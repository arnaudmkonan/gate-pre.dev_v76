"""
Auto-Linker Service - Automatically groups documents into shipments.

Uses extracted DocumentKeys to find documents that share identifiers
(Entry#, BOL#, Container#, etc.) and groups them into Shipment records.
"""
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone
from uuid import UUID
from decimal import Decimal
from collections import defaultdict

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.document_key import DocumentKey, KeyType, KEY_PRIORITY
from app.models.gold_records import Shipment, ShipmentDocument, ShipmentStatus, LinkMethod
from app.models.raw_file import RawFile

logger = logging.getLogger(__name__)


class AutoLinkerService:
    """
    Service for automatically linking documents into shipments.
    
    Flow:
    1. Find documents with shared keys (Entry#, BOL#, Container#, PO#)
    2. Group documents that share at least one key into clusters
    3. Create or update Shipment records for each cluster
    4. Create ShipmentDocument links with metadata
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def link_document(
        self,
        document_id: UUID,
        keys: List[DocumentKey] = None
    ) -> Optional[Shipment]:
        """
        Link a single document to an existing or new shipment.
        
        Args:
            document_id: The document to link
            keys: Pre-extracted keys (if None, will query from DB)
            
        Returns:
            The Shipment the document was linked to, or None if no links found
        """
        # Get keys for document if not provided
        if keys is None:
            keys = await self._get_document_keys(document_id)
        
        if not keys:
            logger.debug(f"No keys found for document {document_id}, cannot link")
            return None
        
        # Find existing shipments that share any of these keys
        matching_shipments = await self._find_matching_shipments(keys, document_id)
        
        if matching_shipments:
            # Link to existing shipment (use the best match)
            shipment = matching_shipments[0][0]
            link_key = matching_shipments[0][1]
            
            await self._link_document_to_shipment(
                shipment, document_id, link_key, LinkMethod.AUTO
            )
            await self._update_shipment_from_keys(shipment, keys)
            
            logger.info(f"Linked document {document_id} to existing shipment {shipment.id} via {link_key.key_type}")
            return shipment
        
        # No matching shipment, find documents that share keys with this one
        related_doc_ids = await self._find_related_documents(keys, document_id)
        
        if related_doc_ids:
            # Create new shipment with this document and related ones
            shipment = await self._create_shipment_from_documents(
                [document_id] + related_doc_ids,
                keys
            )
            logger.info(f"Created new shipment {shipment.id} with {len(related_doc_ids) + 1} documents")
            return shipment
        
        # No related documents - create single-document shipment or leave orphan
        # For now, create a single-document shipment
        shipment = await self._create_shipment_from_documents([document_id], keys)
        logger.info(f"Created new single-document shipment {shipment.id}")
        return shipment
    
    async def run_batch_linking(
        self,
        document_ids: List[UUID] = None,
        only_unlinked: bool = True
    ) -> Dict[str, Any]:
        """
        Run batch auto-linking on multiple documents.
        
        Args:
            document_ids: Specific documents to process (None = all)
            only_unlinked: Only process documents not yet in any shipment
            
        Returns:
            Summary of linking results
        """
        results = {
            "processed": 0,
            "linked": 0,
            "new_shipments": 0,
            "updated_shipments": 0,
            "orphans": 0,
            "errors": []
        }
        
        # Get documents to process
        query = select(DocumentKey.document_id).distinct()
        
        if only_unlinked:
            # Subquery for documents already linked
            linked_subquery = select(ShipmentDocument.document_id).distinct()
            query = query.where(~DocumentKey.document_id.in_(linked_subquery))
        
        if document_ids:
            query = query.where(DocumentKey.document_id.in_(document_ids))
        
        result = await self.db.execute(query)
        doc_ids = [row[0] for row in result.all()]
        
        logger.info(f"Auto-linker processing {len(doc_ids)} documents")
        
        for doc_id in doc_ids:
            try:
                results["processed"] += 1
                shipment = await self.link_document(doc_id)
                
                if shipment:
                    results["linked"] += 1
                else:
                    results["orphans"] += 1
                    
            except Exception as e:
                logger.error(f"Error linking document {doc_id}: {e}")
                results["errors"].append({
                    "document_id": str(doc_id),
                    "error": str(e)
                })
        
        await self.db.commit()
        return results
    
    async def get_orphan_documents(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get documents that have keys but are not linked to any shipment.
        """
        # Subquery for documents already linked
        linked_subquery = select(ShipmentDocument.document_id).distinct()
        
        # Documents with keys but not linked
        query = (
            select(
                DocumentKey.document_id,
                func.count(DocumentKey.id).label('key_count'),
                func.array_agg(DocumentKey.key_type.distinct()).label('key_types')
            )
            .where(~DocumentKey.document_id.in_(linked_subquery))
            .group_by(DocumentKey.document_id)
            .order_by(func.count(DocumentKey.id).desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "document_id": str(row[0]),
                "key_count": row[1],
                "key_types": row[2] or []
            }
            for row in rows
        ]
    
    async def get_link_suggestions(
        self,
        document_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get suggested shipments for an orphan document to be linked to.
        """
        keys = await self._get_document_keys(document_id)
        
        if not keys:
            return []
        
        suggestions = []
        matching_shipments = await self._find_matching_shipments(keys, document_id)
        
        for shipment, link_key in matching_shipments[:limit]:
            suggestions.append({
                "shipment_id": str(shipment.id),
                "shipment_name": shipment.name or f"Shipment {shipment.reference_num or shipment.id}",
                "match_key_type": link_key.key_type,
                "match_key_value": link_key.key_value,
                "confidence": link_key.confidence,
                "document_count": shipment.document_count
            })
        
        return suggestions
    
    async def merge_shipments(
        self,
        target_shipment_id: UUID,
        source_shipment_ids: List[UUID]
    ) -> Shipment:
        """
        Merge multiple shipments into one.
        
        All documents from source shipments are moved to target.
        Source shipments are deleted.
        """
        # Get target shipment
        target = await self.db.get(Shipment, target_shipment_id)
        if not target:
            raise ValueError(f"Target shipment {target_shipment_id} not found")
        
        for source_id in source_shipment_ids:
            source = await self.db.get(Shipment, source_id)
            if not source:
                continue
            
            # Update ShipmentDocument records to point to target
            await self.db.execute(
                ShipmentDocument.__table__.update()
                .where(ShipmentDocument.shipment_id == source_id)
                .values(shipment_id=target_shipment_id)
            )
            
            # Merge key identifiers
            if source.entry_number and not target.entry_number:
                target.entry_number = source.entry_number
            if source.bol_number and not target.bol_number:
                target.bol_number = source.bol_number
            if source.awb_number and not target.awb_number:
                target.awb_number = source.awb_number
            
            # Merge arrays
            target.container_numbers = list(set(
                (target.container_numbers or []) + (source.container_numbers or [])
            ))
            target.po_numbers = list(set(
                (target.po_numbers or []) + (source.po_numbers or [])
            ))
            
            # Delete source shipment
            await self.db.delete(source)
        
        # Update document count
        await self._update_shipment_document_count(target)
        
        await self.db.commit()
        return target
    
    # ========================================================================
    # Private helper methods
    # ========================================================================
    
    async def _get_document_keys(self, document_id: UUID) -> List[DocumentKey]:
        """Get all keys for a document."""
        result = await self.db.execute(
            select(DocumentKey)
            .where(DocumentKey.document_id == document_id)
        )
        return list(result.scalars().all())
    
    async def _find_matching_shipments(
        self,
        keys: List[DocumentKey],
        exclude_document_id: UUID = None
    ) -> List[Tuple[Shipment, DocumentKey]]:
        """
        Find existing shipments that share any of the given keys.
        
        Returns list of (Shipment, matching_key) tuples, sorted by key priority.
        """
        matches = []
        
        for key in sorted(keys, key=lambda k: KEY_PRIORITY.get(KeyType(k.key_type), 99)):
            # Look for shipments with this key in their denormalized fields
            query = select(Shipment)
            
            if key.key_type == KeyType.ENTRY_NUM.value:
                query = query.where(Shipment.entry_number == key.key_value_normalized)
            elif key.key_type == KeyType.BOL_NUM.value:
                query = query.where(Shipment.bol_number == key.key_value_normalized)
            elif key.key_type == KeyType.AWB_NUM.value:
                query = query.where(Shipment.awb_number == key.key_value_normalized)
            elif key.key_type == KeyType.CONTAINER_NUM.value:
                query = query.where(Shipment.container_numbers.contains([key.key_value_normalized]))
            elif key.key_type == KeyType.PO_NUM.value:
                query = query.where(Shipment.po_numbers.contains([key.key_value_normalized]))
            else:
                continue  # Skip keys without denormalized fields
            
            result = await self.db.execute(query)
            for shipment in result.scalars().all():
                if (shipment, key) not in matches:
                    matches.append((shipment, key))
        
        return matches
    
    async def _find_related_documents(
        self,
        keys: List[DocumentKey],
        exclude_document_id: UUID
    ) -> List[UUID]:
        """Find other documents that share any of these keys."""
        related_ids = set()
        
        for key in keys:
            # Find documents with the same key
            result = await self.db.execute(
                select(DocumentKey.document_id)
                .where(
                    DocumentKey.key_type == key.key_type,
                    DocumentKey.key_value_normalized == key.key_value_normalized,
                    DocumentKey.document_id != exclude_document_id
                )
            )
            for row in result.all():
                related_ids.add(row[0])
        
        return list(related_ids)
    
    async def _create_shipment_from_documents(
        self,
        document_ids: List[UUID],
        keys: List[DocumentKey]
    ) -> Shipment:
        """Create a new shipment and link documents to it."""
        # Determine primary linking key
        primary_key = self._get_primary_key(keys)
        
        # Build shipment name
        if primary_key:
            name = f"{primary_key.key_type.replace('_', ' ').title()}: {primary_key.key_value}"
        else:
            name = f"Shipment {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        
        # Create shipment
        shipment = Shipment(
            name=name,
            primary_key_type=primary_key.key_type if primary_key else None,
            primary_key_value=primary_key.key_value if primary_key else None,
            status=ShipmentStatus.PARTIAL.value,
            document_count=len(document_ids),
            document_types=[]
        )
        
        # Populate denormalized fields from keys
        await self._update_shipment_from_keys(shipment, keys)
        
        self.db.add(shipment)
        await self.db.flush()  # Get shipment ID
        
        # Link all documents
        for doc_id in document_ids:
            link = ShipmentDocument(
                shipment_id=shipment.id,
                document_id=doc_id,
                linked_by_key_type=primary_key.key_type if primary_key else None,
                linked_by_key_value=primary_key.key_value if primary_key else None,
                link_confidence=primary_key.confidence if primary_key else 0.5,
                link_method=LinkMethod.AUTO.value
            )
            self.db.add(link)
        
        await self.db.commit()
        return shipment
    
    async def _link_document_to_shipment(
        self,
        shipment: Shipment,
        document_id: UUID,
        link_key: DocumentKey,
        method: LinkMethod
    ):
        """Create a link between document and shipment."""
        # Check if already linked
        existing = await self.db.execute(
            select(ShipmentDocument)
            .where(
                ShipmentDocument.shipment_id == shipment.id,
                ShipmentDocument.document_id == document_id
            )
        )
        if existing.scalar_one_or_none():
            return  # Already linked
        
        link = ShipmentDocument(
            shipment_id=shipment.id,
            document_id=document_id,
            linked_by_key_type=link_key.key_type,
            linked_by_key_value=link_key.key_value,
            link_confidence=link_key.confidence,
            link_method=method.value
        )
        self.db.add(link)
        
        # Update document count
        await self._update_shipment_document_count(shipment)
    
    async def _update_shipment_from_keys(
        self,
        shipment: Shipment,
        keys: List[DocumentKey]
    ):
        """Update shipment's denormalized fields from document keys."""
        for key in keys:
            if key.key_type == KeyType.ENTRY_NUM.value:
                if not shipment.entry_number:
                    shipment.entry_number = key.key_value_normalized or key.key_value
            elif key.key_type == KeyType.BOL_NUM.value:
                if not shipment.bol_number:
                    shipment.bol_number = key.key_value_normalized or key.key_value
            elif key.key_type == KeyType.AWB_NUM.value:
                if not shipment.awb_number:
                    shipment.awb_number = key.key_value_normalized or key.key_value
            elif key.key_type == KeyType.CONTAINER_NUM.value:
                normalized = key.key_value_normalized or key.key_value
                if not shipment.container_numbers:
                    shipment.container_numbers = []
                if normalized not in shipment.container_numbers:
                    shipment.container_numbers = list(shipment.container_numbers) + [normalized]
            elif key.key_type == KeyType.PO_NUM.value:
                normalized = key.key_value_normalized or key.key_value
                if not shipment.po_numbers:
                    shipment.po_numbers = []
                if normalized not in shipment.po_numbers:
                    shipment.po_numbers = list(shipment.po_numbers) + [normalized]
            elif key.key_type == KeyType.IMPORTER_NAME.value:
                if not shipment.importer_name:
                    shipment.importer_name = key.key_value
            elif key.key_type == KeyType.VENDOR_NAME.value:
                if not shipment.exporter_name:
                    shipment.exporter_name = key.key_value
            elif key.key_type == KeyType.MANUFACTURER_NAME.value:
                if not shipment.manufacturer_name:
                    shipment.manufacturer_name = key.key_value
    
    async def _update_shipment_document_count(self, shipment: Shipment):
        """Update the document count on a shipment."""
        result = await self.db.execute(
            select(func.count())
            .select_from(ShipmentDocument)
            .where(ShipmentDocument.shipment_id == shipment.id)
        )
        shipment.document_count = result.scalar_one()
    
    def _get_primary_key(self, keys: List[DocumentKey]) -> Optional[DocumentKey]:
        """Get the strongest (highest priority) key from a list."""
        if not keys:
            return None
        
        sorted_keys = sorted(
            keys,
            key=lambda k: (KEY_PRIORITY.get(KeyType(k.key_type), 99), -k.confidence)
        )
        return sorted_keys[0]


# Factory function
def get_auto_linker(db: AsyncSession) -> AutoLinkerService:
    """Create an AutoLinkerService instance."""
    return AutoLinkerService(db)
