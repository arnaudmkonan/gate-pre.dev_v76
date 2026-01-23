"""
Golden Record Service.

Manages entity deduplication, merge/split operations, and Golden Record lifecycle.
Implements DM-015 from the PRD.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple
from difflib import SequenceMatcher

from sqlalchemy import select, func, or_, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.silver_records import Party, Product, EntityLink

logger = logging.getLogger(__name__)


class GoldenRecordService:
    """
    Service for managing Golden Records (canonical master entities).
    
    Key operations:
    - Find duplicate candidates using fuzzy matching
    - Merge entities into a single Golden Record
    - Split incorrectly merged entities
    - Track merge history via EntityLink
    """

    # Similarity threshold for fuzzy matching (0.0 - 1.0)
    SIMILARITY_THRESHOLD = 0.85

    # --- Duplicate Detection ---

    @staticmethod
    async def find_party_duplicates(
        session: AsyncSession,
        limit: int = 50,
        min_similarity: float = 0.85
    ) -> List[Dict[str, Any]]:
        """
        Find potential duplicate Party records.
        
        Uses a combination of:
        1. Exact alias overlap
        2. Fuzzy name matching (SequenceMatcher)
        3. Tax ID matching
        
        Returns:
            List of candidate pairs with similarity scores
        """
        # Fetch all parties (in production, paginate or use blocking)
        result = await session.execute(
            select(Party).order_by(Party.created_at)
        )
        parties = result.scalars().all()
        
        candidates = []
        seen_pairs = set()
        
        for i, p1 in enumerate(parties):
            for p2 in parties[i + 1:]:
                # Skip if already merged (same golden_record_id)
                if p1.golden_record_id and p1.golden_record_id == p2.golden_record_id:
                    continue
                
                # Create unique pair key
                pair_key = tuple(sorted([str(p1.id), str(p2.id)]))
                if pair_key in seen_pairs:
                    continue
                
                # Calculate similarity
                similarity, match_reason = GoldenRecordService._calculate_party_similarity(p1, p2)
                
                if similarity >= min_similarity:
                    seen_pairs.add(pair_key)
                    candidates.append({
                        "entity_type": "party",
                        "entity_1": {
                            "id": str(p1.id),
                            "canonical_name": p1.canonical_name,
                            "party_type": p1.party_type,
                            "tax_id": p1.tax_id,
                            "aliases": p1.aliases or [],
                        },
                        "entity_2": {
                            "id": str(p2.id),
                            "canonical_name": p2.canonical_name,
                            "party_type": p2.party_type,
                            "tax_id": p2.tax_id,
                            "aliases": p2.aliases or [],
                        },
                        "similarity": round(similarity, 3),
                        "match_reason": match_reason,
                    })
                    
                    if len(candidates) >= limit:
                        return candidates
        
        return candidates

    @staticmethod
    def _calculate_party_similarity(p1: Party, p2: Party) -> Tuple[float, str]:
        """Calculate similarity score between two parties."""
        # 1. Tax ID match (strongest signal)
        if p1.tax_id and p2.tax_id and p1.tax_id == p2.tax_id:
            return 1.0, "tax_id_match"
        
        # 2. Exact name match
        if p1.canonical_name.lower() == p2.canonical_name.lower():
            return 1.0, "exact_name_match"
        
        # 3. Alias overlap
        aliases_1 = set(a.lower() for a in (p1.aliases or []))
        aliases_2 = set(a.lower() for a in (p2.aliases or []))
        
        if aliases_1 & aliases_2:
            return 0.95, "alias_overlap"
        
        # 4. Name in other's aliases
        if p1.canonical_name.lower() in aliases_2 or p2.canonical_name.lower() in aliases_1:
            return 0.92, "name_in_alias"
        
        # 5. Fuzzy name match
        ratio = SequenceMatcher(
            None, 
            p1.canonical_name.lower(), 
            p2.canonical_name.lower()
        ).ratio()
        
        return ratio, "fuzzy_name_match"

    @staticmethod
    async def find_product_duplicates(
        session: AsyncSession,
        limit: int = 50,
        min_similarity: float = 0.85
    ) -> List[Dict[str, Any]]:
        """Find potential duplicate Product records."""
        result = await session.execute(
            select(Product).order_by(Product.created_at)
        )
        products = result.scalars().all()
        
        candidates = []
        seen_pairs = set()
        
        for i, p1 in enumerate(products):
            for p2 in products[i + 1:]:
                if p1.golden_record_id and p1.golden_record_id == p2.golden_record_id:
                    continue
                
                pair_key = tuple(sorted([str(p1.id), str(p2.id)]))
                if pair_key in seen_pairs:
                    continue
                
                similarity, match_reason = GoldenRecordService._calculate_product_similarity(p1, p2)
                
                if similarity >= min_similarity:
                    seen_pairs.add(pair_key)
                    candidates.append({
                        "entity_type": "product",
                        "entity_1": {
                            "id": str(p1.id),
                            "description": p1.description,
                            "hs_code": p1.hs_code,
                        },
                        "entity_2": {
                            "id": str(p2.id),
                            "description": p2.description,
                            "hs_code": p2.hs_code,
                        },
                        "similarity": round(similarity, 3),
                        "match_reason": match_reason,
                    })
                    
                    if len(candidates) >= limit:
                        return candidates
        
        return candidates

    @staticmethod
    def _calculate_product_similarity(p1: Product, p2: Product) -> Tuple[float, str]:
        """Calculate similarity score between two products."""
        # HS Code match (6-digit level)
        if p1.hs_code and p2.hs_code:
            if p1.hs_code[:6] == p2.hs_code[:6]:
                # Check description similarity too
                desc_ratio = SequenceMatcher(
                    None,
                    p1.description.lower(),
                    p2.description.lower()
                ).ratio()
                if desc_ratio > 0.7:
                    return 0.95, "hs_code_and_description_match"
        
        # Fuzzy description match
        ratio = SequenceMatcher(
            None,
            p1.description.lower(),
            p2.description.lower()
        ).ratio()
        
        return ratio, "fuzzy_description_match"

    # --- Merge Operations ---

    @staticmethod
    async def merge_parties(
        session: AsyncSession,
        survivor_id: uuid.UUID,
        victim_id: uuid.UUID,
        merge_aliases: bool = True
    ) -> Dict[str, Any]:
        """
        Merge two Party records into one (survivor).
        
        The victim's data is absorbed into the survivor:
        - Aliases are combined
        - EntityLinks pointing to victim are updated to point to survivor
        - Victim's golden_record_id is set to survivor's ID
        
        Args:
            session: Database session
            survivor_id: ID of the party to keep
            victim_id: ID of the party to merge into survivor
            merge_aliases: Whether to combine alias lists
            
        Returns:
            Merge result summary
        """
        # Fetch both parties
        survivor = await session.get(Party, survivor_id)
        victim = await session.get(Party, victim_id)
        
        if not survivor or not victim:
            return {"status": "error", "message": "One or both parties not found"}
        
        if survivor_id == victim_id:
            return {"status": "error", "message": "Cannot merge a party with itself"}
        
        # Combine aliases
        if merge_aliases:
            combined_aliases = set(survivor.aliases or [])
            combined_aliases.update(victim.aliases or [])
            combined_aliases.add(victim.canonical_name)  # Add victim's name as alias
            survivor.aliases = list(combined_aliases)
        
        # Update victim's golden_record_id to point to survivor
        victim.golden_record_id = survivor_id
        
        # Update EntityLinks: point victim references to survivor
        await session.execute(
            update(EntityLink)
            .where(EntityLink.target_entity_id == victim_id)
            .values(target_entity_id=survivor_id)
        )
        
        # Create merge link for audit trail
        merge_link = EntityLink(
            source_entity_id=victim_id,
            target_entity_id=survivor_id,
            link_type="merged_into",
            confidence=1.0,
            resolution_method="manual_merge"
        )
        session.add(merge_link)
        
        await session.commit()
        
        logger.info(f"Merged Party {victim_id} into {survivor_id}")
        
        return {
            "status": "success",
            "survivor_id": str(survivor_id),
            "victim_id": str(victim_id),
            "combined_aliases": survivor.aliases
        }

    @staticmethod
    async def merge_products(
        session: AsyncSession,
        survivor_id: uuid.UUID,
        victim_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Merge two Product records into one."""
        survivor = await session.get(Product, survivor_id)
        victim = await session.get(Product, victim_id)
        
        if not survivor or not victim:
            return {"status": "error", "message": "One or both products not found"}
        
        if survivor_id == victim_id:
            return {"status": "error", "message": "Cannot merge a product with itself"}
        
        # Combine aliases
        combined_aliases = set(survivor.aliases or [])
        combined_aliases.update(victim.aliases or [])
        combined_aliases.add(victim.description)
        survivor.aliases = list(combined_aliases)
        
        # Inherit HS code if survivor doesn't have one
        if not survivor.hs_code and victim.hs_code:
            survivor.hs_code = victim.hs_code
        
        victim.golden_record_id = survivor_id
        
        await session.execute(
            update(EntityLink)
            .where(EntityLink.target_entity_id == victim_id)
            .values(target_entity_id=survivor_id)
        )
        
        merge_link = EntityLink(
            source_entity_id=victim_id,
            target_entity_id=survivor_id,
            link_type="merged_into",
            confidence=1.0,
            resolution_method="manual_merge"
        )
        session.add(merge_link)
        
        await session.commit()
        
        logger.info(f"Merged Product {victim_id} into {survivor_id}")
        
        return {
            "status": "success",
            "survivor_id": str(survivor_id),
            "victim_id": str(victim_id)
        }

    # --- Split Operations ---

    @staticmethod
    async def split_party(
        session: AsyncSession,
        party_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Undo a merge by clearing the golden_record_id.
        
        Note: This only clears the pointer. EntityLinks are NOT reverted
        as that would require more complex history tracking.
        """
        party = await session.get(Party, party_id)
        
        if not party:
            return {"status": "error", "message": "Party not found"}
        
        if not party.golden_record_id:
            return {"status": "error", "message": "Party is not merged"}
        
        old_golden = party.golden_record_id
        party.golden_record_id = None
        
        await session.commit()
        
        return {
            "status": "success",
            "party_id": str(party_id),
            "unlinked_from": str(old_golden)
        }

    # --- Stats ---

    @staticmethod
    async def get_golden_record_stats(session: AsyncSession) -> Dict[str, Any]:
        """Get statistics about Golden Records."""
        # Count parties
        total_parties = (await session.execute(
            select(func.count(Party.id))
        )).scalar() or 0
        
        merged_parties = (await session.execute(
            select(func.count(Party.id)).where(Party.golden_record_id.isnot(None))
        )).scalar() or 0
        
        # Count products
        total_products = (await session.execute(
            select(func.count(Product.id))
        )).scalar() or 0
        
        merged_products = (await session.execute(
            select(func.count(Product.id)).where(Product.golden_record_id.isnot(None))
        )).scalar() or 0
        
        return {
            "parties": {
                "total": total_parties,
                "merged": merged_parties,
                "unique": total_parties - merged_parties
            },
            "products": {
                "total": total_products,
                "merged": merged_products,
                "unique": total_products - merged_products
            }
        }
