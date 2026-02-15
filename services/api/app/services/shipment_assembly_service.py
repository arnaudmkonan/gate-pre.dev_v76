"""
Shipment Assembly Service

Analyzes extracted document data and creates shipment suggestions
by grouping documents that share common identifiers.

Supports three modes:
- AUTO: Automatically create shipments from suggestions
- MANUAL: Create suggestions for user review
- ASSISTED: Auto-create high-confidence, flag low-confidence for review
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from collections import defaultdict

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.document_metadata import DocumentMetadata
from app.models.extraction_result import ExtractionResult
from app.models.gold_records import Shipment, ShipmentDocument
from app.models.shipment_suggestions import (
    ShipmentSuggestion, 
    ShipmentSuggestionDocument,
    ClientAssemblyPreference,
    SuggestionStatus,
    AssemblyMode
)

logger = logging.getLogger(__name__)


class ShipmentAssemblyService:
    """
    Service for analyzing documents and creating shipment suggestions.
    """
    
    # Identifiers used for matching documents
    LINKING_IDENTIFIERS = [
        "master_bl_number", "master_bl",
        "house_bl_number", "house_bl",
        "container", "container_1", "container_2",
        "booking_number", "booking",
        "invoice_number",
    ]
    
    # Minimum confidence to create a suggestion
    MIN_CONFIDENCE = 0.5
    
    @staticmethod
    async def analyze_documents(
        session: AsyncSession,
        document_ids: List[UUID],
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze documents and return suggested shipment groupings.
        
        Args:
            session: Database session
            document_ids: List of document IDs to analyze
            tenant_id: Optional tenant isolation
            
        Returns:
            List of suggested shipment groupings
        """
        # Get extraction results for all documents
        extractions = await ShipmentAssemblyService._get_document_extractions(
            session, document_ids
        )
        
        if not extractions:
            logger.info(f"No extractions found for documents")
            return []
        
        # Group documents by shared identifiers
        groupings = ShipmentAssemblyService._group_by_identifiers(extractions)
        
        # Convert to suggestions
        suggestions = []
        for key, group in groupings.items():
            if len(group["document_ids"]) >= 1:  # At least 1 document with identifier
                suggestion = ShipmentAssemblyService._create_suggestion_dict(key, group)
                if suggestion["confidence_score"] >= ShipmentAssemblyService.MIN_CONFIDENCE:
                    suggestions.append(suggestion)
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x["confidence_score"], reverse=True)
        
        return suggestions
    
    @staticmethod
    async def _get_document_extractions(
        session: AsyncSession,
        document_ids: List[UUID]
    ) -> Dict[UUID, Dict[str, Any]]:
        """Get extraction results for documents organized by document ID."""
        from sqlalchemy import or_
        
        # First try to get trade_document extractions (preferred structured data)
        result = await session.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id.in_(document_ids),
                ExtractionResult.extraction_type == "trade_document"
            )
        )
        extraction_records = list(result.scalars().all())
        
        # If no trade extractions, fall back to any extractions
        if not extraction_records:
            result = await session.execute(
                select(ExtractionResult).where(
                    ExtractionResult.document_id.in_(document_ids)
                )
            )
            extraction_records = list(result.scalars().all())
        
        # Also get document metadata for filenames
        doc_result = await session.execute(
            select(DocumentMetadata).where(
                DocumentMetadata.id.in_(document_ids)
            )
        )
        documents = {doc.id: doc for doc in doc_result.scalars().all()}
        
        # Organize by document
        extractions = {}
        for doc_id in document_ids:
            extractions[doc_id] = {
                "document_id": doc_id,
                "filename": documents.get(doc_id).filename if documents.get(doc_id) else None,
                "fields": {}
            }
        
        for ext in extraction_records:
            if ext.document_id in extractions:
                field_name = ext.field_name.lower().replace(" ", "_")
                extractions[ext.document_id]["fields"][field_name] = ext.field_value
                
                # Also store document type if extracted
                if field_name == "document_type":
                    extractions[ext.document_id]["document_type"] = ext.field_value
        
        return extractions
    
    @staticmethod
    def _normalize_value(value) -> Optional[str]:
        """Normalize a field value to a string for comparison."""
        if value is None:
            return None
        if isinstance(value, list):
            # If it's a list, take the first element
            return str(value[0]) if value else None
        if isinstance(value, dict):
            # If it's a dict with a value key, use that
            return str(value.get("value") or value.get("name") or list(value.values())[0] if value else None)
        # Clean up JSON string quotes
        result = str(value).strip('"').strip("'").strip()
        return result if result else None
    
    @staticmethod
    def _group_by_identifiers(
        extractions: Dict[UUID, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Group documents by shared linking identifiers.
        
        Priority:
        1. Master BL (strongest link)
        2. Container Number
        3. House BL
        4. Booking Number
        """
        # Index documents by identifier
        by_master_bl = defaultdict(list)
        by_container = defaultdict(list)
        by_house_bl = defaultdict(list)
        by_booking = defaultdict(list)
        
        normalize = ShipmentAssemblyService._normalize_value
        
        for doc_id, data in extractions.items():
            fields = data.get("fields", {})
            
            # Check for master BL
            master_bl = normalize(
                fields.get("master_bl_number") or 
                fields.get("master_bl") or 
                fields.get("master_bol")
            )
            if master_bl:
                by_master_bl[master_bl].append(doc_id)
            
            # Check for containers
            for key, value in fields.items():
                if "container" in key and value:
                    container_val = normalize(value)
                    if container_val:
                        by_container[container_val].append(doc_id)
            
            # Check for house BL
            house_bl = normalize(
                fields.get("house_bl_number") or 
                fields.get("house_bl") or 
                fields.get("house_bol")
            )
            if house_bl:
                by_house_bl[house_bl].append(doc_id)
            
            # Check for booking
            booking = normalize(fields.get("booking_number") or fields.get("booking"))
            if booking:
                by_booking[booking].append(doc_id)
        
        # Create groupings - prioritize Master BL
        groupings = {}
        processed_docs = set()
        
        # First pass: Master BL groups
        for master_bl, doc_ids in by_master_bl.items():
            if not master_bl or len(master_bl) < 3:
                continue
            key = f"mbl:{master_bl}"
            containers = set()
            house_bls = set()
            suggested_details = {}
            
            for doc_id in doc_ids:
                processed_docs.add(doc_id)
                fields = extractions[doc_id].get("fields", {})
                
                # Collect containers from this BL
                for k, v in fields.items():
                    if "container" in k and v:
                        c_val = normalize(v)
                        if c_val:
                            containers.add(c_val)
                
                # Collect house BLs
                hbl = normalize(fields.get("house_bl_number") or fields.get("house_bl"))
                if hbl:
                    house_bls.add(hbl)
                
                # Extract shipment details
                for detail_field in ["vessel_name", "vessel", "port_of_loading", "port_of_discharge", 
                                      "eta", "consignee", "shipper"]:
                    if detail_field in fields and fields[detail_field]:
                        suggested_details[detail_field] = normalize(fields[detail_field]) or fields[detail_field]
            
            groupings[key] = {
                "master_bl": master_bl,
                "house_bls": list(house_bls),
                "containers": list(containers),
                "document_ids": doc_ids,
                "documents": [
                    {
                        "id": str(doc_id),
                        "filename": extractions[doc_id].get("filename"),
                        "document_type": extractions[doc_id].get("document_type", "Unknown"),
                        "fields": extractions[doc_id].get("fields", {})
                    }
                    for doc_id in doc_ids
                ],
                "match_type": "master_bl",
                "suggested_details": suggested_details
            }
        
        # Second pass: Container groups (for docs not in Master BL groups)
        for container, doc_ids in by_container.items():
            unprocessed = [d for d in doc_ids if d not in processed_docs]
            if not unprocessed or not container or len(container) < 3:
                continue
            
            key = f"cnt:{container}"
            for doc_id in unprocessed:
                processed_docs.add(doc_id)
            
            suggested_details = {}
            for doc_id in unprocessed:
                fields = extractions[doc_id].get("fields", {})
                for detail_field in ["vessel_name", "consignee", "shipper"]:
                    if detail_field in fields and fields[detail_field]:
                        suggested_details[detail_field] = normalize(fields[detail_field]) or fields[detail_field]
            
            groupings[key] = {
                "master_bl": None,
                "house_bls": [],
                "containers": [container],
                "document_ids": unprocessed,
                "documents": [
                    {
                        "id": str(doc_id),
                        "filename": extractions[doc_id].get("filename"),
                        "document_type": extractions[doc_id].get("document_type", "Unknown"),
                        "fields": extractions[doc_id].get("fields", {})
                    }
                    for doc_id in unprocessed
                ],
                "match_type": "container",
                "suggested_details": suggested_details
            }
        
        return groupings
    
    @staticmethod
    def _create_suggestion_dict(key: str, group: Dict) -> Dict[str, Any]:
        """Create a suggestion dictionary from a grouping."""
        doc_count = len(group["document_ids"])
        has_master_bl = bool(group.get("master_bl"))
        has_containers = bool(group.get("containers"))
        
        # Calculate confidence based on quality of match
        confidence = 0.5
        match_reasons = []
        
        if has_master_bl:
            confidence += 0.3
            match_reasons.append(f"Master BL: {group['master_bl']}")
        
        if has_containers:
            confidence += 0.1
            match_reasons.append(f"Container(s): {', '.join(group['containers'][:3])}")
        
        if doc_count >= 2:
            confidence += 0.05 * min(doc_count - 1, 4)  # Up to +0.2 for 5+ docs
            match_reasons.append(f"{doc_count} documents matched")
        
        # Check for diverse document types (better confidence)
        doc_types = set(d.get("document_type") for d in group.get("documents", []))
        if len(doc_types) >= 2:
            confidence += 0.05
            match_reasons.append(f"Multiple doc types: {', '.join(list(doc_types)[:3])}")
        
        confidence = min(confidence, 1.0)
        
        return {
            "key": key,
            "master_bl": group.get("master_bl"),
            "house_bls": group.get("house_bls", []),
            "containers": group.get("containers", []),
            "document_ids": [str(d) for d in group["document_ids"]],
            "documents": group.get("documents", []),
            "confidence_score": round(confidence, 2),
            "match_reasons": match_reasons,
            "suggested_details": group.get("suggested_details", {}),
            "match_type": group.get("match_type"),
        }
    
    @staticmethod
    async def create_suggestions(
        session: AsyncSession,
        suggestions: List[Dict[str, Any]],
        tenant_id: Optional[str] = None,
        auto_mode: bool = False
    ) -> List[ShipmentSuggestion]:
        """
        Create ShipmentSuggestion records from analysis results.
        
        If auto_mode is True, suggestions are auto-accepted and shipments created.
        """
        created_suggestions = []
        
        for sugg in suggestions:
            # Check if suggestion already exists for this master BL
            if sugg.get("master_bl"):
                existing = await session.execute(
                    select(ShipmentSuggestion).where(
                        and_(
                            ShipmentSuggestion.master_bl == sugg["master_bl"],
                            ShipmentSuggestion.status == SuggestionStatus.PENDING
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    logger.info(f"Suggestion already exists for {sugg['master_bl']}")
                    continue
            
            suggestion = ShipmentSuggestion(
                master_bl=sugg.get("master_bl"),
                house_bl=sugg.get("house_bls", [None])[0] if sugg.get("house_bls") else None,
                container_numbers=sugg.get("containers"),
                confidence_score=sugg.get("confidence_score", 0.5),
                match_reasons=sugg.get("match_reasons"),
                document_ids=[UUID(d) if isinstance(d, str) else d for d in sugg.get("document_ids", [])],
                suggested_details=sugg.get("suggested_details"),
                status=SuggestionStatus.PENDING,
                tenant_id=tenant_id,
            )
            
            session.add(suggestion)
            created_suggestions.append(suggestion)
            
            # Create document links
            for doc in sugg.get("documents", []):
                doc_link = ShipmentSuggestionDocument(
                    suggestion_id=suggestion.id,
                    document_id=UUID(doc["id"]) if isinstance(doc["id"], str) else doc["id"],
                    document_type=doc.get("document_type"),
                    extracted_identifiers=doc.get("fields"),
                    match_confidence=sugg.get("confidence_score", 1.0)
                )
                session.add(doc_link)
        
        await session.commit()
        
        # If auto mode, accept all suggestions
        if auto_mode and created_suggestions:
            for suggestion in created_suggestions:
                await ShipmentAssemblyService.accept_suggestion(
                    session, suggestion.id, reviewed_by="system_auto"
                )
        
        return created_suggestions
    
    @staticmethod
    async def accept_suggestion(
        session: AsyncSession,
        suggestion_id: UUID,
        reviewed_by: str = "user"
    ) -> Optional[Shipment]:
        """
        Accept a suggestion and create a Shipment.
        """
        result = await session.execute(
            select(ShipmentSuggestion).where(ShipmentSuggestion.id == suggestion_id)
        )
        suggestion = result.scalar_one_or_none()
        
        if not suggestion:
            return None
        
        if suggestion.status != SuggestionStatus.PENDING:
            logger.warning(f"Suggestion {suggestion_id} is not pending")
            return None
        
        # Create shipment
        details = suggestion.suggested_details or {}
        shipment = Shipment(
            primary_key_type="master_bl" if suggestion.master_bl else "container",
            primary_key_value=suggestion.master_bl or (suggestion.container_numbers[0] if suggestion.container_numbers else "unknown"),
            bol_number=suggestion.master_bl,
            origin=details.get("port_of_loading"),
            destination=details.get("port_of_discharge"),
            importer_name=details.get("consignee"),
            exporter_name=details.get("shipper"),
            container_numbers=suggestion.container_numbers or [],
            status="partial",  # Starts as partial until validated
        )
        session.add(shipment)
        await session.flush()  # Get shipment ID
        
        # Store document IDs in the legacy documents array field
        # Note: ShipmentDocument references raw_files, not document_metadata
        # So we use the documents array field directly
        shipment.documents = list(suggestion.document_ids)
        shipment.document_count = len(suggestion.document_ids)
        
        # Update suggestion
        suggestion.status = SuggestionStatus.ACCEPTED
        suggestion.reviewed_at = datetime.now(timezone.utc)
        suggestion.reviewed_by = reviewed_by
        suggestion.created_shipment_id = shipment.id
        
        await session.commit()
        
        logger.info(f"Created shipment {shipment.id} from suggestion {suggestion_id}")
        return shipment
    
    @staticmethod
    async def reject_suggestion(
        session: AsyncSession,
        suggestion_id: UUID,
        rejection_reason: str = None,
        reviewed_by: str = "user"
    ) -> bool:
        """Reject a shipment suggestion."""
        result = await session.execute(
            select(ShipmentSuggestion).where(ShipmentSuggestion.id == suggestion_id)
        )
        suggestion = result.scalar_one_or_none()
        
        if not suggestion or suggestion.status != SuggestionStatus.PENDING:
            return False
        
        suggestion.status = SuggestionStatus.REJECTED
        suggestion.reviewed_at = datetime.now(timezone.utc)
        suggestion.reviewed_by = reviewed_by
        suggestion.rejection_reason = rejection_reason
        
        await session.commit()
        return True
    
    @staticmethod
    async def get_pending_suggestions(
        session: AsyncSession,
        tenant_id: Optional[str] = None,
        limit: int = 50
    ) -> List[ShipmentSuggestion]:
        """Get all pending suggestions."""
        query = select(ShipmentSuggestion).where(
            ShipmentSuggestion.status == SuggestionStatus.PENDING
        )
        
        if tenant_id:
            query = query.where(ShipmentSuggestion.tenant_id == tenant_id)
        
        query = query.order_by(ShipmentSuggestion.confidence_score.desc()).limit(limit)
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_client_assembly_mode(
        session: AsyncSession,
        client_id: str
    ) -> AssemblyMode:
        """Get the assembly mode preference for a client."""
        result = await session.execute(
            select(ClientAssemblyPreference).where(
                ClientAssemblyPreference.client_id == client_id
            )
        )
        pref = result.scalar_one_or_none()
        
        return pref.assembly_mode if pref else AssemblyMode.MANUAL
    
    @staticmethod
    async def set_client_assembly_mode(
        session: AsyncSession,
        client_id: str,
        mode: AssemblyMode
    ) -> ClientAssemblyPreference:
        """Set the assembly mode preference for a client."""
        result = await session.execute(
            select(ClientAssemblyPreference).where(
                ClientAssemblyPreference.client_id == client_id
            )
        )
        pref = result.scalar_one_or_none()
        
        if pref:
            pref.assembly_mode = mode
            pref.updated_at = datetime.now(timezone.utc)
        else:
            pref = ClientAssemblyPreference(
                client_id=client_id,
                assembly_mode=mode
            )
            session.add(pref)
        
        await session.commit()
        return pref


# Sync version for use in Celery workers
class ShipmentAssemblyServiceSync:
    """Synchronous version for Celery workers."""
    
    @staticmethod
    def analyze_and_create_suggestions(
        session: Session,
        document_ids: List[UUID],
        tenant_id: Optional[str] = None,
        auto_mode: bool = False
    ) -> List[ShipmentSuggestion]:
        """Analyze documents and create suggestions synchronously."""
        from sqlalchemy import select
        
        # Get extractions
        result = session.execute(
            select(ExtractionResult).where(
                ExtractionResult.document_id.in_(document_ids)
            )
        )
        extraction_records = result.scalars().all()
        
        # Get documents
        doc_result = session.execute(
            select(DocumentMetadata).where(
                DocumentMetadata.id.in_(document_ids)
            )
        )
        documents = {doc.id: doc for doc in doc_result.scalars().all()}
        
        # Build extractions dict
        extractions = {}
        for doc_id in document_ids:
            extractions[doc_id] = {
                "document_id": doc_id,
                "filename": documents.get(doc_id).filename if documents.get(doc_id) else None,
                "fields": {}
            }
        
        for ext in extraction_records:
            if ext.document_id in extractions:
                field_name = ext.field_name.lower().replace(" ", "_")
                extractions[ext.document_id]["fields"][field_name] = ext.field_value
                if field_name == "document_type":
                    extractions[ext.document_id]["document_type"] = ext.field_value
        
        # Group and create suggestions
        groupings = ShipmentAssemblyService._group_by_identifiers(extractions)
        
        suggestions = []
        for key, group in groupings.items():
            if len(group["document_ids"]) >= 1:
                sugg_dict = ShipmentAssemblyService._create_suggestion_dict(key, group)
                if sugg_dict["confidence_score"] >= ShipmentAssemblyService.MIN_CONFIDENCE:
                    suggestions.append(sugg_dict)
        
        if not suggestions:
            return []
        
        # Create suggestion records
        created = []
        for sugg in suggestions:
            suggestion = ShipmentSuggestion(
                master_bl=sugg.get("master_bl"),
                house_bl=sugg.get("house_bls", [None])[0] if sugg.get("house_bls") else None,
                container_numbers=sugg.get("containers"),
                confidence_score=sugg.get("confidence_score", 0.5),
                match_reasons=sugg.get("match_reasons"),
                document_ids=[UUID(d) if isinstance(d, str) else d for d in sugg.get("document_ids", [])],
                suggested_details=sugg.get("suggested_details"),
                status=SuggestionStatus.ACCEPTED if auto_mode else SuggestionStatus.PENDING,
                tenant_id=tenant_id,
            )
            session.add(suggestion)
            created.append(suggestion)
        
        session.commit()
        
        # If auto mode, create shipments
        if auto_mode:
            for suggestion in created:
                ShipmentAssemblyServiceSync._create_shipment_from_suggestion(
                    session, suggestion
                )
        
        return created
    
    @staticmethod
    def _create_shipment_from_suggestion(
        session: Session,
        suggestion: ShipmentSuggestion
    ) -> Shipment:
        """Create a shipment from an accepted suggestion."""
        details = suggestion.suggested_details or {}
        
        shipment = Shipment(
            primary_key_type="master_bl" if suggestion.master_bl else "container",
            primary_key_value=suggestion.master_bl or (suggestion.container_numbers[0] if suggestion.container_numbers else "unknown"),
            bol_number=suggestion.master_bl,
            origin=details.get("port_of_loading"),
            destination=details.get("port_of_discharge"),
            importer_name=details.get("consignee"),
            exporter_name=details.get("shipper"),
            container_numbers=suggestion.container_numbers or [],
            status="partial",
        )
        session.add(shipment)
        session.flush()
        
        # Store document IDs in the legacy documents array field
        shipment.documents = list(suggestion.document_ids)
        shipment.document_count = len(suggestion.document_ids)
        
        suggestion.created_shipment_id = shipment.id
        session.commit()
        
        return shipment
