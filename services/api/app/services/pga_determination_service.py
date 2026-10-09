"""
PGA Determination Engine  (Task 3.2)

Determines which Partner Government Agencies (PGAs) have regulatory
jurisdiction over a shipment based on HTS chapter, product description,
and country of origin.

~30% of US imports require filings with agencies beyond CBP:
  - FDA   (21 CFR): Food, drugs, cosmetics, medical devices, tobacco
  - EPA   (40 CFR): Chemicals under TSCA, vehicles, engines, pesticides
  - USDA/APHIS: Plants, animals, wood products (Lacey Act)
  - FWS   (50 CFR): Wildlife products, CITES species
  - ATF              Firearms, ammunition, explosives
  - CPSC             Consumer products, toys, electronics for children
  - DOE              Energy-consuming products, appliances
  - NHTSA            Motor vehicles, safety equipment

This engine implements a rules-based HTS chapter → PGA mapping and
provides the data structure for the API endpoint and ABI filing.

Design: Data-driven rules allow future updates without code changes.
Add new chapters to PGA_CHAPTER_RULES; no other changes needed.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule Data Structures
# ---------------------------------------------------------------------------

@dataclass
class PGARequirement:
    """Describes a single PGA filing requirement for a shipment line."""
    agency: str                        # "FDA", "EPA", "USDA", etc.
    program_code: str                  # CBP PGA program code (e.g. "FDA01")
    requirement_type: str              # "notice", "permit", "license", "declaration"
    description: str                   # Human-readable description
    regulation: str                    # Authorising CFR citation
    is_mandatory: bool = True          # False = conditional on specific products
    filing_form: Optional[str] = None  # e.g. "FDA Prior Notice", "EPA Form 3520-1"
    notes: Optional[str] = None        # Broker guidance notes


@dataclass
class PGADetermination:
    """Result of a PGA determination for a shipment or entry line."""
    hts_code: str
    hts_chapter: str
    requirements: List[PGARequirement] = field(default_factory=list)
    is_pga_required: bool = False
    agencies_involved: List[str] = field(default_factory=list)
    advisory_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hts_code": self.hts_code,
            "hts_chapter": self.hts_chapter,
            "is_pga_required": self.is_pga_required,
            "agencies_involved": self.agencies_involved,
            "requirements": [
                {
                    "agency": r.agency,
                    "program_code": r.program_code,
                    "requirement_type": r.requirement_type,
                    "description": r.description,
                    "regulation": r.regulation,
                    "is_mandatory": r.is_mandatory,
                    "filing_form": r.filing_form,
                    "notes": r.notes,
                }
                for r in self.requirements
            ],
            "advisory_notes": self.advisory_notes,
        }


# ---------------------------------------------------------------------------
# HTS Chapter → PGA Rules
# Each key is a 2-digit HTS chapter prefix.
# ---------------------------------------------------------------------------

PGA_CHAPTER_RULES: Dict[str, List[PGARequirement]] = {
    # ---- FDA — Food, Drugs, Devices, Cosmetics, Tobacco ----------------
    "02": [PGARequirement("FDA", "FDA01", "notice", "Meat and edible meat offal", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "03": [PGARequirement("FDA", "FDA01", "notice", "Fish and crustaceans", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "04": [PGARequirement("FDA", "FDA01", "notice", "Dairy produce, eggs", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "07": [PGARequirement("FDA", "FDA01", "notice", "Edible vegetables", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "08": [PGARequirement("FDA", "FDA01", "notice", "Edible fruits and nuts", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "09": [PGARequirement("FDA", "FDA01", "notice", "Coffee, tea, spices", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "10": [PGARequirement("FDA", "FDA01", "notice", "Cereals / grains", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "11": [PGARequirement("FDA", "FDA01", "notice", "Milling products, flour", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "15": [PGARequirement("FDA", "FDA01", "notice", "Animal or vegetable fats / oils", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "16": [PGARequirement("FDA", "FDA01", "notice", "Preparations of meat or fish", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "17": [PGARequirement("FDA", "FDA01", "notice", "Sugar and sugar confectionery", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "18": [PGARequirement("FDA", "FDA01", "notice", "Cocoa and cocoa preparations", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "19": [PGARequirement("FDA", "FDA01", "notice", "Preparations of cereals / baked goods", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "20": [PGARequirement("FDA", "FDA01", "notice", "Preparations of vegetables / fruit", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "21": [PGARequirement("FDA", "FDA01", "notice", "Miscellaneous edible preparations", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "22": [PGARequirement("FDA", "FDA01", "notice", "Beverages, spirits, vinegar", "21 CFR 1.279", filing_form="FDA Prior Notice")],
    "24": [PGARequirement("FDA", "FDA02", "notice", "Tobacco and tobacco substitutes", "21 CFR 1101", filing_form="FDA Prior Notice", notes="CTP Program")],
    "29": [PGARequirement("FDA", "FDA04", "permit", "Organic chemicals (bulk drugs)", "21 CFR 312", is_mandatory=False, notes="Only if pharmaceutical-grade")],
    "30": [PGARequirement("FDA", "FDA03", "permit", "Pharmaceutical products", "21 CFR 312 / 314", filing_form="FDA Drug Registration", notes="Requires importer drug registration")],
    "33": [PGARequirement("FDA", "FDA05", "declaration", "Essential oils, perfumery, cosmetics", "21 CFR 700", filing_form="FDA Cosmetics Declaration")],
    "90": [PGARequirement("FDA", "FDA06", "registration", "Optical / medical instruments (if medical device)", "21 CFR 807", is_mandatory=False, filing_form="FDA Device Registration", notes="Applies if classified as medical device")],

    # ---- USDA / APHIS — Plants, Animals, Wood Products -----------------
    "01": [PGARequirement("USDA", "APH01", "permit", "Live animals", "7 CFR 93", filing_form="VS Form 17-129")],
    "06": [PGARequirement("USDA", "APH02", "permit", "Live trees, plants, flowers", "7 CFR 319", filing_form="APHIS Plant Import Permit")],
    "12": [PGARequirement("USDA", "APH03", "declaration", "Oil seeds, miscellaneous grains / plants", "7 CFR 319.37", filing_form="Lacey Act Declaration (PPQ Form 505)")],
    "44": [PGARequirement("USDA", "APH04", "declaration", "Wood and articles of wood", "16 USC 3372", filing_form="Lacey Act Declaration (PPQ Form 505)", notes="Lacey Act — all wood/timber products")],
    "47": [PGARequirement("USDA", "APH04", "declaration", "Pulp / paper (if containing plant material)", "16 USC 3372", filing_form="Lacey Act Declaration", is_mandatory=False)],
    "94": [PGARequirement("USDA", "APH04", "declaration", "Furniture (if wooden)", "16 USC 3372", filing_form="Lacey Act Declaration (PPQ Form 505)", is_mandatory=False, notes="Required for articles containing wood")],

    # ---- EPA — Chemicals, Vehicles, Engines, Pesticides ----------------
    "28": [PGARequirement("EPA", "EPA01", "notice", "Inorganic chemicals (TSCA)", "15 USC 2601", filing_form="EPA TSCA Certification")],
    "29": [PGARequirement("EPA", "EPA01", "notice", "Organic chemicals (TSCA)", "15 USC 2601", filing_form="EPA TSCA Certification")],
    "38": [PGARequirement("EPA", "EPA02", "notice", "Pesticides / herbicides", "7 USC 136", filing_form="EPA Pesticide Registration", notes="Must be registered with EPA prior to import")],
    "87": [PGARequirement("EPA", "EPA03", "certification", "Motor vehicles and parts", "40 CFR 85", filing_form="EPA Form 3520-1 (vehicles) / 3520-21 (engines)", notes="Applies to motor vehicles and off-road engines")],
    "84": [PGARequirement("EPA", "EPA04", "certification", "Engines (non-vehicle, >25hp)", "40 CFR 89/1039", is_mandatory=False, filing_form="EPA Engine Certification", notes="Applies to non-road diesel/gasoline engines")],

    # ---- FWS — Wildlife, CITES -----------------------------------------
    "41": [PGARequirement("FWS", "FWS01", "permit", "Raw hides, leather (if exotic)", "16 USC 1538", is_mandatory=False, filing_form="CITES Permit", notes="Required for CITES-listed species only")],
    "42": [PGARequirement("FWS", "FWS01", "permit", "Travel goods (if exotic leather)", "16 USC 1538", is_mandatory=False, filing_form="CITES Permit")],
    "43": [PGARequirement("FWS", "FWS02", "permit", "Furskins and artificial fur", "16 USC 1538", is_mandatory=False, filing_form="CITES Permit")],
    "97": [PGARequirement("FWS", "FWS03", "permit", "Works of art (if containing wildlife)", "16 USC 1538", is_mandatory=False)],

    # ---- ATF — Firearms, Ammunition ------------------------------------
    "93": [PGARequirement("ATF", "ATF01", "license", "Arms and ammunition", "27 CFR 447", filing_form="ATF Form 6 (Import Permit)", notes="Requires advance ATF import permit")],

    # ---- CPSC — Consumer Product Safety --------------------------------
    "39": [PGARequirement("CPSC", "CPS01", "declaration", "Plastics / children's products", "15 USC 2063", is_mandatory=False, filing_form="CPSC Certificate of Conformity", notes="Required for children's products")],
    "69": [PGARequirement("CPSC", "CPS02", "declaration", "Ceramic ware (lead content)", "15 USC 1278a", is_mandatory=False, notes="Lead content declaration for ceramic tableware")],
    "73": [PGARequirement("CPSC", "CPS03", "declaration", "Steel articles (if children's products)", "15 USC 2063", is_mandatory=False)],
    "85": [PGARequirement("CPSC", "CPS04", "declaration", "Electrical equipment / electronics (children's)", "15 USC 2063", is_mandatory=False, filing_form="CPSC Certificate of Conformity")],

    # ---- NHTSA — Motor Vehicle Safety ----------------------------------
    "87": [PGARequirement("NHTSA", "NHS01", "certification", "Motor vehicles", "49 CFR 591", filing_form="NHTSA HS-7 Declaration", notes="All motor vehicles must meet FMVSS or be exempt")],

    # ---- DOE — Energy Efficiency ---------------------------------------
    "84": [PGARequirement("DOE", "DOE01", "certification", "Appliances and equipment (energy standards)", "10 CFR 430", is_mandatory=False, notes="Applies to covered energy-consuming products")],
    "85": [PGARequirement("DOE", "DOE01", "certification", "Electrical motors / transformers", "10 CFR 431", is_mandatory=False)],
}

# Chapters that typically need NO PGA filing (non-sensitive goods)
NON_PGA_CHAPTERS: Set[str] = {
    "25", "26",   # Mineral products
    "32",         # Pigments, paints, inks
    "34",         # Soap, waxes
    "36",         # Explosives (ATF usually, but chapter is misc)
    "40",         # Rubber
    "45",         # Cork
    "46",         # Straw / wicker
    "48", "49",   # Paper
    "52", "53", "54", "55", "56", "57", "58", "59", "60", "61", "62", "63",  # Textiles
    "64", "65", "66", "67",  # Footwear, headgear
    "68", "70",   # Stone, glass
    "71",         # Precious metals / jewelry
    "72", "74", "75", "76", "78", "79", "80", "81", "82", "83",  # Base metals
    "86", "88", "89",  # Rail, aircraft, vessels
    "91", "92",   # Clocks, musical instruments
    "95", "96",   # Toys, miscellaneous
    "98", "99",   # Special classifications
}


class PGADeterminationEngine:
    """
    Determines PGA filing requirements from HTS codes.

    Usage:
        engine = PGADeterminationEngine()
        determination = engine.determine(hts_code="0302.11.0000")
        if determination.is_pga_required:
            for req in determination.requirements:
                print(req.agency, req.filing_form)
    """

    def determine(
        self,
        hts_code: str,
        product_description: Optional[str] = None,
        country_of_origin: Optional[str] = None,
    ) -> PGADetermination:
        """
        Determine PGA requirements for a single HTS code.

        Args:
            hts_code: 10-digit HTS code (dots and spaces stripped internally).
            product_description: Freetext description — used for conditional rules.
            country_of_origin: ISO 2-char COO — some rules are COO-specific.

        Returns:
            PGADetermination with requirements list.
        """
        chapter = self._extract_chapter(hts_code)
        requirements = []
        agencies = set()
        notes = []

        if chapter in NON_PGA_CHAPTERS:
            return PGADetermination(
                hts_code=hts_code,
                hts_chapter=chapter,
                is_pga_required=False,
                advisory_notes=["Chapter typically exempt from PGA requirements"],
            )

        # Look up chapter rules
        chapter_rules = PGA_CHAPTER_RULES.get(chapter, [])
        for rule in chapter_rules:
            # For conditional rules, check description keywords
            if not rule.is_mandatory and product_description:
                if not self._description_matches(rule, product_description):
                    notes.append(
                        f"{rule.agency}: Conditional requirement — verify if '{rule.description}' applies"
                    )
                    continue
            requirements.append(rule)
            agencies.add(rule.agency)

        # Some chapters appear in multiple agency lists (e.g., ch29 → FDA + EPA)
        # Deduplicate by (agency, program_code)
        seen = set()
        unique_reqs = []
        for r in requirements:
            key = (r.agency, r.program_code)
            if key not in seen:
                seen.add(key)
                unique_reqs.append(r)

        return PGADetermination(
            hts_code=hts_code,
            hts_chapter=chapter,
            requirements=unique_reqs,
            is_pga_required=len(unique_reqs) > 0,
            agencies_involved=sorted(agencies),
            advisory_notes=notes,
        )

    def determine_for_entry(
        self,
        line_items: List[Dict],
    ) -> Dict[str, PGADetermination]:
        """
        Determine PGA requirements for all line items in an entry.

        Args:
            line_items: List of dicts with keys: hts_code, description, country_of_origin

        Returns:
            Dict mapping hts_code → PGADetermination
        """
        results = {}
        for item in line_items:
            hts = item.get("hts_code", "")
            if hts:
                results[hts] = self.determine(
                    hts_code=hts,
                    product_description=item.get("description"),
                    country_of_origin=item.get("country_of_origin"),
                )
        return results

    def get_all_agencies(self, determinations: List[PGADetermination]) -> List[str]:
        """Return sorted list of all agencies required across multiple determinations."""
        agencies: Set[str] = set()
        for det in determinations:
            agencies.update(det.agencies_involved)
        return sorted(agencies)

    def has_pga_requirement(self, hts_code: str) -> bool:
        """Quick check: does this HTS code require any PGA filing?"""
        return self.determine(hts_code).is_pga_required

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_chapter(self, hts_code: str) -> str:
        """Extract 2-digit HTS chapter from a full HTS code."""
        clean = re.sub(r'[\s.]', '', hts_code)
        return clean[:2] if len(clean) >= 2 else clean

    def _description_matches(self, rule: PGARequirement, description: str) -> bool:
        """
        Check if product description contains keywords suggesting the
        conditional PGA rule applies.
        """
        desc_lower = description.lower()
        # Keyword hints by agency / program
        hints = {
            "FDA06": ["medical", "diagnostic", "surgical", "device", "implant"],
            "EPA04": ["engine", "generator", "compressor", "diesel", "gasoline"],
            "DOE01": ["appliance", "refrigerator", "washer", "dryer", "furnace", "lamp", "motor"],
            "FWS01": ["crocodile", "alligator", "snake", "python", "exotic", "cites"],
            "CPSC01": ["children", "child", "baby", "toy", "infant"],
        }
        relevant_hints = hints.get(rule.program_code, [])
        if not relevant_hints:
            return True  # No specific hints — assume applies
        return any(h in desc_lower for h in relevant_hints)


# Convenience import alias
import re  # noqa: E402 (needed by _extract_chapter)


# Top-level convenience function for direct use
def determine_pga_requirements(hts_code: str, **kwargs) -> PGADetermination:
    """Module-level convenience wrapper."""
    return PGADeterminationEngine().determine(hts_code, **kwargs)
