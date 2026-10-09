"""
GATE Platform — Entity Resolution Service.

Resolves extracted Bronze-layer data into normalized Silver-layer entities
(Party, Product, Address) and creates EntityLink records.

Matching strategy:
 - Case-insensitive, whitespace-normalised exact match (current default).
 - Resolution method string records how the match was made, so switching to
   pg_trgm / rapidfuzz fuzzy matching in the future requires only   
   changing the match query and the resolution_method label.
"""
import logging
import re
import uuid
from typing import Dict, Optional, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_result import ExtractionResult
from app.models.silver_records import Party, Product, Address, EntityLink

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Return a normalised comparison key: lowercase, collapsed whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


class EntityResolutionService:
    """
    Service for resolving extracted data (Bronze) into normalized entities (Silver).

    Uses case-insensitive matching so 'ACME CORP' and 'Acme Corp' resolve
    to the same Party record.  The canonical_name stored is the first-seen
    form of the name; subsequent matches update the aliases list.
    """

    @staticmethod
    async def resolve_document_entities(session: AsyncSession, document_id: str) -> Dict[str, Any]:
        """
        Resolve all entities for a specific document.

        Args:
            session: Database session
            document_id: ID of the document to process

        Returns:
            Dict summarising resolution results
        """
        query = select(ExtractionResult).where(
            ExtractionResult.document_id == uuid.UUID(document_id),
        )
        result = await session.execute(query)
        extractions = result.scalars().all()

        if not extractions:
            logger.info(f"No extractions found for document {document_id}")
            return {"status": "no_extractions"}

        resolved_count = 0
        new_parties = 0
        new_products = 0

        for extraction in extractions:
            # Only resolve high-confidence or human-reviewed items.
            if extraction.confidence < 0.7 and extraction.status == "auto":
                continue

            val = extraction.final_value or extraction.field_value
            if not val:
                continue

            # Strip spurious JSON string-wrapping ("value" → value).
            if isinstance(val, str) and val.startswith('"') and val.endswith('"'):
                val = val[1:-1]

            field_name = extraction.field_name.lower()

            # --- Party Resolution ---
            party_keywords = [
                "shipper", "consignee", "vendor", "supplier", "importer",
                "exporter", "manufacturer", "buyer", "seller", "carrier",
                "organization",
            ]
            if any(k in field_name for k in party_keywords):
                party = await EntityResolutionService._resolve_party(
                    session, val, field_name, extraction.id
                )
                if party:
                    resolved_count += 1
                    new_parties += 1

            # --- Product Resolution ---
            product_keywords = [
                "product_desc", "commodity", "goods_desc", "merchandise", "product",
            ]
            if any(k in field_name for k in product_keywords):
                product = await EntityResolutionService._resolve_product(
                    session, val, extraction.id
                )
                if product:
                    resolved_count += 1
                    new_products += 1

            # --- Address Resolution ---
            address_keywords = ["location", "address", "port", "destination", "origin"]
            if any(k in field_name for k in address_keywords):
                address = await EntityResolutionService._resolve_address(
                    session, val, extraction.id
                )
                if address:
                    resolved_count += 1

        await session.commit()

        logger.info(
            f"Entity resolution for {document_id}: "
            f"{resolved_count} resolved, {new_parties} parties, {new_products} products"
        )

        return {
            "status": "completed",
            "resolved_entities": resolved_count,
            "new_parties": new_parties,
            "new_products": new_products,
            "document_id": document_id,
        }

    @staticmethod
    async def _resolve_party(
        session: AsyncSession,
        name: str,
        role_hint: str,
        extraction_id: uuid.UUID,
    ) -> Optional[Party]:
        """Find or create a Party record and link it.

        Uses case-insensitive matching via func.lower() so 'ACME Corp' and
        'acme corp' resolve to the same record.
        """
        if not isinstance(name, str):
            return None

        name = name.strip()
        if not name:
            return None

        normalised_name = _normalize(name)

        # Case-insensitive lookup — prevents duplicate records for the same
        # legal entity written with different capitalisation.
        query = select(Party).where(func.lower(Party.canonical_name) == normalised_name)
        result = await session.execute(query)
        party = result.scalars().first()

        if not party:
            party_type = "individual" if "person" in role_hint else "organization"
            party = Party(
                canonical_name=name,  # Store the original case
                party_type=party_type,
                aliases=[name],
            )
            session.add(party)
            await session.flush()
            logger.info(f"Created new Silver Party: {name}")
        elif name not in (party.aliases or []):
            # Record new capitalisation variant as an alias.
            party.aliases = list(party.aliases or []) + [name]

        link = EntityLink(
            source_entity_id=extraction_id,
            target_entity_id=party.id,
            link_type="extraction_to_party",
            confidence=1.0,
            resolution_method="case_insensitive_exact",
        )
        session.add(link)

        return party

    @staticmethod
    async def _resolve_product(
        session: AsyncSession,
        description: str,
        extraction_id: uuid.UUID,
    ) -> Optional[Product]:
        """Find or create a Product record and link it."""
        if not isinstance(description, str):
            return None

        description = description.strip()
        if len(description) < 3:
            return None

        normalised_desc = _normalize(description)

        query = select(Product).where(func.lower(Product.description) == normalised_desc)
        result = await session.execute(query)
        product = result.scalars().first()

        if not product:
            product = Product(
                description=description,
                aliases=[description],
            )
            session.add(product)
            await session.flush()
            logger.info(f"Created new Silver Product: {description}")
        elif description not in (product.aliases or []):
            product.aliases = list(product.aliases or []) + [description]

        link = EntityLink(
            source_entity_id=extraction_id,
            target_entity_id=product.id,
            link_type="extraction_to_product",
            confidence=1.0,
            resolution_method="case_insensitive_exact",
        )
        session.add(link)

        return product

    @staticmethod
    async def _resolve_address(
        session: AsyncSession,
        address_text: str,
        extraction_id: uuid.UUID,
    ) -> Optional[Address]:
        """Find or create an Address record and link it."""
        if not isinstance(address_text, str):
            return None

        address_text = address_text.strip()
        if len(address_text) < 5:
            return None

        normalised_addr = _normalize(address_text)

        query = select(Address).where(
            func.lower(Address.normalized_address) == normalised_addr
        )
        result = await session.execute(query)
        address = result.scalars().first()

        if not address:
            address = Address(
                street=address_text,
                normalized_address=address_text,
                city=None,
                state=None,
                country="US",  # Default; override with country extraction when available
                postal_code=None,
            )
            session.add(address)
            await session.flush()
            logger.info(f"Created new Silver Address: {address_text[:60]}")

        link = EntityLink(
            source_entity_id=extraction_id,
            target_entity_id=address.id,
            link_type="extraction_to_address",
            confidence=1.0,
            resolution_method="case_insensitive_exact",
        )
        session.add(link)

        return address
