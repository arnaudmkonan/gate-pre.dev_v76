"""
Reference Data Service for Trade Compliance
Provides search, screening, and management of OFAC SDN, HTS codes, and NAICS codes.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from difflib import SequenceMatcher

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reference_data import OFACSdn, HTSCode, NAICSCode, ComplianceScreen

logger = logging.getLogger(__name__)


class ReferenceDataService:
    """Service for managing and searching reference data (OFAC, HTS, NAICS)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== HTS Code Operations ====================

    async def search_hts_codes(
        self,
        query: str,
        chapter: Optional[int] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search HTS codes by code or description.
        
        Args:
            query: Search term (HTS code or description text)
            chapter: Optional filter by chapter number
            limit: Maximum results to return
            
        Returns:
            List of matching HTS codes with duty rates
        """
        # Build search conditions
        conditions = []
        
        # Check if query looks like an HTS code (contains digits/dots)
        if any(c.isdigit() for c in query):
            conditions.append(HTSCode.hts_code.ilike(f"%{query}%"))
        
        # Always search description
        conditions.append(HTSCode.description.ilike(f"%{query}%"))
        
        stmt = select(HTSCode).where(or_(*conditions))
        
        if chapter:
            stmt = stmt.where(HTSCode.chapter == chapter)
            
        stmt = stmt.limit(limit)
        
        result = await self.db.execute(stmt)
        codes = result.scalars().all()
        
        return [
            {
                "id": str(code.id),
                "hts_code": code.hts_code,
                "description": code.description,
                "chapter": code.chapter,
                "duty_rate": code.duty_rate,
                "duty_rate_percent": float(code.duty_rate_percent) if code.duty_rate_percent else None,
                "special_rates": code.special_rates,
            }
            for code in codes
        ]

    async def get_hts_code(self, hts_code: str) -> Optional[Dict[str, Any]]:
        """Get a specific HTS code by its code string."""
        # Normalize code (remove dots for comparison)
        normalized = hts_code.replace(".", "")
        
        stmt = select(HTSCode).where(
            func.replace(HTSCode.hts_code, ".", "") == normalized
        )
        result = await self.db.execute(stmt)
        code = result.scalar_one_or_none()
        
        if not code:
            return None
            
        return {
            "id": str(code.id),
            "hts_code": code.hts_code,
            "description": code.description,
            "chapter": code.chapter,
            "duty_rate": code.duty_rate,
            "duty_rate_percent": float(code.duty_rate_percent) if code.duty_rate_percent else None,
            "special_rates": code.special_rates,
            "notes": code.notes,
        }

    async def get_hts_stats(self) -> Dict[str, Any]:
        """Get statistics about HTS codes in the database."""
        total_stmt = select(func.count()).select_from(HTSCode)
        chapter_stmt = select(
            HTSCode.chapter,
            func.count().label("count")
        ).group_by(HTSCode.chapter).order_by(HTSCode.chapter)
        
        total_result = await self.db.execute(total_stmt)
        chapter_result = await self.db.execute(chapter_stmt)
        
        return {
            "total_codes": total_result.scalar(),
            "by_chapter": [
                {"chapter": row.chapter, "count": row.count}
                for row in chapter_result
            ]
        }

    # ==================== OFAC SDN Operations ====================

    async def screen_entity(
        self,
        name: str,
        entity_type: Optional[str] = None,
        id_number: Optional[str] = None,
        threshold: float = 0.85
    ) -> Dict[str, Any]:
        """
        Screen an entity against the OFAC SDN list.
        Uses fuzzy matching for name comparison.
        
        Args:
            name: Entity name to screen
            entity_type: Optional type filter (Individual, Entity, Vessel)
            id_number: Optional ID number (passport, tax ID) to match
            threshold: Minimum similarity score for name matches (0-1)
            
        Returns:
            Screening result with matches and risk level
        """
        matches = []
        
        # First, try exact ID match if provided
        if id_number:
            # Search in id_numbers JSONB array
            stmt = select(OFACSdn).where(
                OFACSdn.id_numbers.cast(str).ilike(f"%{id_number}%")
            )
            result = await self.db.execute(stmt)
            id_matches = result.scalars().all()
            
            for sdn in id_matches:
                matches.append({
                    "sdn_id": str(sdn.id),
                    "name": sdn.sdn_name,
                    "type": sdn.sdn_type,
                    "program": sdn.program,
                    "match_type": "id_match",
                    "score": 1.0,
                    "aliases": sdn.aliases or [],
                })

        # Name-based fuzzy matching
        # For performance, first get candidates with similar prefixes
        name_normalized = name.upper().strip()
        prefix = name_normalized[:3] if len(name_normalized) >= 3 else name_normalized
        
        stmt = select(OFACSdn).where(
            or_(
                func.upper(OFACSdn.sdn_name).like(f"{prefix}%"),
                func.upper(func.array_to_string(OFACSdn.aliases, " ")).like(f"%{prefix}%"),
            )
        )
        
        if entity_type:
            stmt = stmt.where(OFACSdn.sdn_type == entity_type)
            
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()
        
        for sdn in candidates:
            # Check main name
            score = SequenceMatcher(None, name_normalized, sdn.sdn_name.upper()).ratio()
            
            # Also check aliases
            alias_scores = []
            for alias in (sdn.aliases or []):
                alias_score = SequenceMatcher(None, name_normalized, alias.upper()).ratio()
                alias_scores.append(alias_score)
            
            best_alias_score = max(alias_scores) if alias_scores else 0
            best_score = max(score, best_alias_score)
            
            if best_score >= threshold:
                # Avoid duplicates from ID matching
                existing_ids = [m["sdn_id"] for m in matches]
                if str(sdn.id) not in existing_ids:
                    matches.append({
                        "sdn_id": str(sdn.id),
                        "name": sdn.sdn_name,
                        "type": sdn.sdn_type,
                        "program": sdn.program,
                        "match_type": "name_match",
                        "score": round(best_score, 3),
                        "aliases": sdn.aliases or [],
                        "nationality": sdn.nationality,
                    })

        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        # Determine risk level
        if any(m["score"] >= 0.98 for m in matches):
            risk_level = "confirmed_match"
        elif matches:
            risk_level = "possible_match"
        else:
            risk_level = "clear"

        return {
            "screened_name": name,
            "matches_found": len(matches),
            "risk_level": risk_level,
            "matches": matches[:10],  # Top 10 matches
            "screened_at": datetime.utcnow().isoformat(),
        }

    async def get_ofac_stats(self) -> Dict[str, Any]:
        """Get statistics about OFAC SDN entries."""
        total_stmt = select(func.count()).select_from(OFACSdn)
        type_stmt = select(
            OFACSdn.sdn_type,
            func.count().label("count")
        ).group_by(OFACSdn.sdn_type)
        program_stmt = select(
            OFACSdn.program,
            func.count().label("count")
        ).group_by(OFACSdn.program).order_by(func.count().desc()).limit(10)
        
        total = await self.db.execute(total_stmt)
        type_result = await self.db.execute(type_stmt)
        program_result = await self.db.execute(program_stmt)
        
        return {
            "total_entries": total.scalar(),
            "by_type": [
                {"type": row.sdn_type, "count": row.count}
                for row in type_result
            ],
            "top_programs": [
                {"program": row.program, "count": row.count}
                for row in program_result
            ]
        }

    # ==================== NAICS Code Operations ====================

    async def search_naics_codes(
        self,
        query: str,
        sector: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search NAICS codes by code or title."""
        conditions = []
        
        if any(c.isdigit() for c in query):
            conditions.append(NAICSCode.naics_code.like(f"{query}%"))
            
        conditions.append(NAICSCode.title.ilike(f"%{query}%"))
        conditions.append(NAICSCode.description.ilike(f"%{query}%"))
        
        stmt = select(NAICSCode).where(or_(*conditions))
        
        if sector:
            stmt = stmt.where(NAICSCode.sector.ilike(f"%{sector}%"))
            
        stmt = stmt.limit(limit)
        
        result = await self.db.execute(stmt)
        codes = result.scalars().all()
        
        return [
            {
                "id": str(code.id),
                "naics_code": code.naics_code,
                "title": code.title,
                "description": code.description,
                "sector": code.sector,
                "level": code.level,
            }
            for code in codes
        ]

    # ==================== Compliance Screen Recording ====================

    async def record_screen(
        self,
        screen_type: str,
        result: Dict[str, Any],
        shipment_id: Optional[UUID] = None,
        party_id: Optional[UUID] = None,
        product_id: Optional[UUID] = None,
    ) -> ComplianceScreen:
        """Record a compliance screening result."""
        risk_level = result.get("risk_level", "clear")
        matches = result.get("matches", [])
        
        screen = ComplianceScreen(
            shipment_id=shipment_id,
            party_id=party_id,
            product_id=product_id,
            screen_type=screen_type,
            result=result,
            risk_level=risk_level,
            matches=matches,
        )
        
        self.db.add(screen)
        await self.db.commit()
        await self.db.refresh(screen)
        
        return screen

    async def get_screening_history(
        self,
        party_id: Optional[UUID] = None,
        shipment_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get screening history for a party or shipment."""
        stmt = select(ComplianceScreen)
        
        if party_id:
            stmt = stmt.where(ComplianceScreen.party_id == party_id)
        if shipment_id:
            stmt = stmt.where(ComplianceScreen.shipment_id == shipment_id)
            
        stmt = stmt.order_by(ComplianceScreen.created_at.desc()).limit(limit)
        
        result = await self.db.execute(stmt)
        screens = result.scalars().all()
        
        return [
            {
                "id": str(s.id),
                "screen_type": s.screen_type,
                "risk_level": s.risk_level,
                "matches_count": len(s.matches or []),
                "resolved": s.resolved,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in screens
        ]


# ==================== Embedded Reference Data ====================
# Common HTS codes for trade compliance (subset for local development)

HTS_CODES_DATA = [
    # Chapter 1 - Live Animals
    ("0101.21.00", "Live horses, purebred breeding animals", 1, "Free", 0.0),
    ("0101.29.00", "Live horses, other than purebred breeding", 1, "Free", 0.0),
    
    # Chapter 22 - Beverages
    ("2201.10.00", "Mineral waters and aerated waters", 22, "Free", 0.0),
    ("2203.00.00", "Beer made from malt", 22, "Free", 0.0),
    ("2204.10.00", "Sparkling wine", 22, "19.8¢/liter", None),
    
    # Chapter 39 - Plastics
    ("3901.10.00", "Polyethylene, specific gravity less than 0.94", 39, "6.5%", 6.5),
    ("3901.20.00", "Polyethylene, specific gravity 0.94 or more", 39, "6.5%", 6.5),
    
    # Chapter 61 - Apparel, Knitted
    ("6109.10.00", "T-shirts, singlets, tank tops, of cotton, knitted", 61, "16.5%", 16.5),
    ("6110.20.10", "Sweaters of cotton, knitted", 61, "16.5%", 16.5),
    
    # Chapter 72 - Iron and Steel (Section 232)
    ("7208.10.15", "Flat-rolled iron/steel, hot-rolled, in coils", 72, "25%", 25.0),
    ("7209.15.00", "Flat-rolled iron/steel, cold-rolled, in coils", 72, "25%", 25.0),
    ("7210.41.00", "Flat-rolled iron/steel, zinc-coated, corrugated", 72, "25%", 25.0),
    
    # Chapter 76 - Aluminum (Section 232 + AD/CVD)
    ("7604.10.10", "Aluminum bars, rods and profiles, alloy", 76, "10%", 10.0),
    ("7604.21.00", "Aluminum profiles, alloy, hollow", 76, "10%", 10.0),
    ("7606.11.30", "Aluminum plates/sheets, alloy, rectangular", 76, "10%", 10.0),
    
    # Chapter 84 - Machinery
    ("8443.31.00", "Printers, copying machines, facsimile machines", 84, "Free", 0.0),
    ("8471.30.01", "Portable digital automatic data processing machines", 84, "Free", 0.0),
    ("8471.41.01", "Other computers comprising CPU and I/O units", 84, "Free", 0.0),
    
    # Chapter 85 - Electronics (Section 301 List 1-4)
    ("8501.31.40", "DC motors, 750W-75kW", 85, "25%", 25.0),
    ("8517.12.00", "Telephones for cellular networks", 85, "Free", 0.0),
    ("8528.71.00", "Video reception apparatus, not incorporating display", 85, "25%", 25.0),
    ("8541.40.60", "Solar cells assembled in modules", 85, "25%", 25.0),
    
    # Chapter 87 - Vehicles
    ("8703.23.00", "Motor cars, spark-ignition, 1500-3000cc", 87, "2.5%", 2.5),
    ("8703.80.00", "Motor vehicles, electric only", 87, "2.5%", 2.5),
    ("8708.10.30", "Bumpers and parts thereof", 87, "25%", 25.0),
    
    # Chapter 94 - Furniture
    ("9401.30.00", "Swivel seats with variable height adjustment", 94, "Free", 0.0),
    ("9403.20.00", "Metal furniture, other", 94, "Free", 0.0),
    ("9403.60.80", "Wooden furniture, other", 94, "Free", 0.0),
]

NAICS_CODES_DATA = [
    # Manufacturing
    ("311", "Food Manufacturing", "Manufacturing"),
    ("312", "Beverage and Tobacco Product Manufacturing", "Manufacturing"),
    ("315", "Apparel Manufacturing", "Manufacturing"),
    ("331", "Primary Metal Manufacturing", "Manufacturing"),
    ("332", "Fabricated Metal Product Manufacturing", "Manufacturing"),
    ("333", "Machinery Manufacturing", "Manufacturing"),
    ("334", "Computer and Electronic Product Manufacturing", "Manufacturing"),
    ("335", "Electrical Equipment and Appliance Manufacturing", "Manufacturing"),
    ("336", "Transportation Equipment Manufacturing", "Manufacturing"),
    ("337", "Furniture and Related Product Manufacturing", "Manufacturing"),
    
    # Wholesale Trade
    ("423", "Merchant Wholesalers, Durable Goods", "Wholesale Trade"),
    ("424", "Merchant Wholesalers, Nondurable Goods", "Wholesale Trade"),
    ("425", "Wholesale Electronic Markets and Agents", "Wholesale Trade"),
    
    # Retail Trade
    ("441", "Motor Vehicle and Parts Dealers", "Retail Trade"),
    ("442", "Furniture and Home Furnishings Stores", "Retail Trade"),
    ("443", "Electronics and Appliance Stores", "Retail Trade"),
    ("444", "Building Material and Garden Equipment Dealers", "Retail Trade"),
    
    # Transportation
    ("481", "Air Transportation", "Transportation and Warehousing"),
    ("482", "Rail Transportation", "Transportation and Warehousing"),
    ("483", "Water Transportation", "Transportation and Warehousing"),
    ("484", "Truck Transportation", "Transportation and Warehousing"),
    ("488", "Support Activities for Transportation", "Transportation and Warehousing"),
    ("493", "Warehousing and Storage", "Transportation and Warehousing"),
]


async def seed_reference_data(db: AsyncSession) -> Dict[str, Any]:
    """
    Seed the database with embedded HTS and NAICS reference data.
    
    Returns:
        Dict with counts of seeded records
    """
    results = {"hts_codes": 0, "naics_codes": 0, "errors": []}
    
    # Seed HTS codes
    for hts_data in HTS_CODES_DATA:
        code, description, chapter, duty_rate, duty_percent = hts_data
        
        # Check if exists
        existing = await db.execute(
            select(HTSCode).where(HTSCode.hts_code == code)
        )
        if existing.scalar_one_or_none():
            continue
            
        hts = HTSCode(
            hts_code=code,
            description=description,
            chapter=chapter,
            duty_rate=duty_rate,
            duty_rate_percent=Decimal(str(duty_percent)) if duty_percent is not None else None,
        )
        db.add(hts)
        results["hts_codes"] += 1
        
    # Seed NAICS codes
    for naics_data in NAICS_CODES_DATA:
        code, title, sector = naics_data
        
        existing = await db.execute(
            select(NAICSCode).where(NAICSCode.naics_code == code)
        )
        if existing.scalar_one_or_none():
            continue
            
        naics = NAICSCode(
            naics_code=code,
            title=title,
            sector=sector,
            level=len(code),
        )
        db.add(naics)
        results["naics_codes"] += 1
    
    await db.commit()
    
    logger.info(f"Seeded {results['hts_codes']} HTS codes and {results['naics_codes']} NAICS codes")
    
    return results
