import logging
import uuid
from typing import Dict, List, Optional, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.extraction_result import ExtractionResult
from app.models.document_metadata import DocumentMetadata
from app.models.silver_records import Party, Product, Address, EntityLink

logger = logging.getLogger(__name__)


class EntityResolutionService:
    """
    Service for resolving extracted data (Bronze) into normalized entities (Silver).
    Implements simple heuristic-based entity resolution.
    """

    @staticmethod
    async def resolve_document_entities(session: AsyncSession, document_id: str) -> Dict[str, Any]:
        """
        Resolve all entities for a specific document.
        
        Args:
            session: Database session
            document_id: ID of the document to process
            
        Returns:
            Dict summarizing resolution results
        """
        # 1. Fetch extracted results
        query = select(ExtractionResult).where(
            ExtractionResult.document_id == uuid.UUID(document_id),
            # Filter for relevant fields only (optimization)
            # In a real system, we might process everything. Here we look for key entities.
            # We assume extraction_type or field_names help identify what to resolve.
        )
        result = await session.execute(query)
        extractions = result.scalars().all()

        if not extractions:
            logger.info(f"No extractions found for document {document_id}")
            return {"status": "no_extractions"}

        resolved_count = 0
        new_parties = 0
        new_products = 0

        # Group extractions by context/parent if possible, but simpler approach:
        # Iterate and map based on known field names.
        
        for extraction in extractions:
            # We only resolve high-confidence or reviewed items
            if extraction.confidence < 0.7 and extraction.status == 'auto':
                continue
                
            val = extraction.final_value or extraction.field_value
            if not val:
                continue

            # Handle JSON-encoded values
            if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
                val = val[1:-1]  # Strip quotes

            field_name = extraction.field_name.lower()
            
            # --- Party Resolution ---
            # Match both: (1) document-specific names and (2) generic entity types
            party_keywords = [
                'shipper', 'consignee', 'vendor', 'supplier', 'importer', 
                'exporter', 'manufacturer', 'buyer', 'seller', 'carrier',
                'organization',  # Generic NER output
            ]
            if any(k in field_name for k in party_keywords):
                # It's likely a company/person
                party = await EntityResolutionService._resolve_party(session, val, field_name, extraction.id)
                if party:
                    resolved_count += 1
                    new_parties += 1
                    
            # --- Product Resolution ---
            product_keywords = [
                'product_desc', 'commodity', 'goods_desc', 'merchandise',
                'product',  # Generic NER output
            ]
            if any(k in field_name for k in product_keywords):
                product = await EntityResolutionService._resolve_product(session, val, extraction.id)
                if product:
                    resolved_count += 1
                    new_products += 1
            
            # --- Address Resolution ---
            address_keywords = ['location', 'address', 'port', 'destination', 'origin']
            if any(k in field_name for k in address_keywords):
                address = await EntityResolutionService._resolve_address(session, val, extraction.id)
                if address:
                    resolved_count += 1

        await session.commit()
        
        logger.info(f"Entity resolution for {document_id}: {resolved_count} resolved, {new_parties} parties, {new_products} products")
        
        return {
            "status": "completed",
            "resolved_entities": resolved_count,
            "new_parties": new_parties,
            "new_products": new_products,
            "document_id": document_id
        }

    @staticmethod
    async def _resolve_party(session: AsyncSession, name: str, role_hint: str, extraction_id: uuid.UUID) -> Optional[Party]:
        """
        Find or create a Party record and link it.
        """
        if not isinstance(name, str):
            # If it's a dict (address object), extracted differently
            return None
            
        name = name.strip()
        if not name:
            return None

        # Check if exists
        query = select(Party).where(Party.canonical_name == name)
        result = await session.execute(query)
        party = result.scalar_one_or_none()
        
        if not party:
            # Create new Party
            party_type = "organization" # Default
            if "person" in role_hint:
                party_type = "individual"
                
            party = Party(
                canonical_name=name,
                party_type=party_type,
                aliases=[name] # Initialize with self as alias
            )
            session.add(party)
            await session.flush() # Get ID
            logger.info(f"Created new Silver Party: {name}")
        
        # Create Link
        link = EntityLink(
            source_entity_id=extraction_id,
            target_entity_id=party.id,
            link_type="extraction_to_party",
            confidence=1.0,
            resolution_method="exact_match"
        )
        session.add(link)
        
        return party

    @staticmethod
    async def _resolve_product(session: AsyncSession, description: str, extraction_id: uuid.UUID) -> Optional[Product]:
        """
        Find or create a Product record and link it.
        """
        if not isinstance(description, str):
            return None
            
        description = description.strip()
        if len(description) < 3:
            return None

        # Check if exists (exact match)
        query = select(Product).where(Product.description == description)
        result = await session.execute(query)
        product = result.scalar_one_or_none()
        
        if not product:
            product = Product(
                description=description,
                aliases=[description]
            )
            session.add(product)
            await session.flush()
            logger.info(f"Created new Silver Product: {description}")
            
        # Create Link
        link = EntityLink(
            source_entity_id=extraction_id,
            target_entity_id=product.id,
            link_type="extraction_to_product",
            confidence=1.0,
            resolution_method="exact_match"
        )
        session.add(link)

        return product

    @staticmethod
    async def _resolve_address(session: AsyncSession, address_text: str, extraction_id: uuid.UUID) -> Optional[Address]:
        """
        Find or create an Address record and link it.
        """
        if not isinstance(address_text, str):
            return None
            
        address_text = address_text.strip()
        if len(address_text) < 5:
            return None

        # Check if exists (exact match on normalized_address)
        query = select(Address).where(Address.normalized_address == address_text)
        result = await session.execute(query)
        address = result.scalar_one_or_none()
        
        if not address:
            address = Address(
                street=address_text,  # Store full text in street field
                normalized_address=address_text,  # Also store as normalized
                city=None,
                state=None,
                country="US",  # Default assumption
                postal_code=None,
            )
            session.add(address)
            await session.flush()
            logger.info(f"Created new Silver Address: {address_text[:50]}...")
            
        # Create Link
        link = EntityLink(
            source_entity_id=extraction_id,
            target_entity_id=address.id,
            link_type="extraction_to_address",
            confidence=1.0,
            resolution_method="exact_match"
        )
        session.add(link)

        return address
