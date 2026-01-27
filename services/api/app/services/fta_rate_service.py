"""
FTA/Preference Program Rates Service.

Enhanced FTA rate lookups with HTS-specific coverage and savings calculation.

Task 2.4 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from decimal import Decimal


# ============================================================================
# FTA HTS Coverage Data
# Not all HTS codes qualify for duty-free under FTAs. This is simplified data.
# In production, this would be a comprehensive database from USTR.
# ============================================================================

# General rule: Most manufactured goods qualify if they meet rules of origin
# Exceptions: Certain agricultural products, textiles (special rules), etc.

FTA_EXCLUSIONS = {
    "USMCA": {
        # Certain dairy products have TRQs (Tariff Rate Quotas)
        "excluded_chapters": ["04"],  # Dairy - limited
        "excluded_headings": ["0401", "0402", "0403", "0405", "0406"],
        # Certain textiles have yarn-forward rules
        "special_rules": ["61", "62", "63"],  # Textiles - special ROO
    },
    "KORUS": {
        "excluded_chapters": [],
        "excluded_headings": ["0401", "0402"],  # Some dairy limited
        "special_rules": ["61", "62"],  # Textiles
    },
    "CAFTA-DR": {
        "excluded_chapters": [],
        "excluded_headings": [],
        "special_rules": ["61", "62", "63"],  # Textiles
    },
}

# FTA preferential rates by HTS chapter
# Format: {chapter: {fta_code: preferential_rate}}
# Rate of 0 means duty-free, rate > 0 is preferential rate
FTA_RATES = {
    # Chapter 84: Machinery
    "84": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
    # Chapter 85: Electrical machinery
    "85": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
    # Chapter 87: Vehicles (special rules for USMCA)
    "87": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
    # Chapter 39: Plastics
    "39": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
    # Chapter 73: Steel articles (still pay Section 232 if applicable)
    "73": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
    # Chapter 94: Furniture
    "94": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
    # Chapter 90: Optical/medical instruments
    "90": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
    # Chapter 40: Rubber
    "40": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
    # Chapter 44: Wood
    "44": {"USMCA": Decimal("0"), "KORUS": Decimal("0"), "CAFTA-DR": Decimal("0"), "Australia": Decimal("0")},
}

# MFN (Most Favored Nation) rates by chapter - simplified
# In production, this comes from the HTS database
MFN_RATES = {
    "84": Decimal("2.5"),   # Machinery
    "85": Decimal("3.5"),   # Electrical
    "87": Decimal("2.5"),   # Vehicles
    "39": Decimal("5.5"),   # Plastics
    "73": Decimal("3.0"),   # Steel articles
    "94": Decimal("4.5"),   # Furniture
    "90": Decimal("3.0"),   # Optical
    "40": Decimal("4.0"),   # Rubber
    "44": Decimal("5.0"),   # Wood
}

# GSP (Generalized System of Preferences) eligible countries
# Note: GSP program has expired/been renewed multiple times. Check current status.
GSP_COUNTRIES = [
    "ID",  # Indonesia
    "IN",  # India (removed 2019, may be reinstated)
    "TH",  # Thailand
    "PH",  # Philippines
    "AR",  # Argentina
    "BR",  # Brazil
    "EC",  # Ecuador
    "PE",  # Peru (also has bilateral FTA)
    "PK",  # Pakistan
    "BD",  # Bangladesh
    "LK",  # Sri Lanka
    "ZA",  # South Africa
    "EG",  # Egypt
    "JO",  # Jordan (also has FTA)
    "TR",  # Turkey
]

# GSP excluded products (import-sensitive)
GSP_EXCLUDED_CHAPTERS = ["61", "62", "63", "64", "42"]  # Textiles, footwear, leather


@dataclass
class FTACheckResult:
    """Result of FTA eligibility check."""
    eligible: bool
    fta_code: Optional[str] = None
    fta_name: Optional[str] = None
    preferential_rate: Optional[float] = None
    mfn_rate: Optional[float] = None
    savings_rate: Optional[float] = None
    savings_amount: Optional[float] = None
    requirements: List[str] = None
    rvc_threshold: Optional[float] = None
    notes: List[str] = None
    
    def __post_init__(self):
        if self.requirements is None:
            self.requirements = []
        if self.notes is None:
            self.notes = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "fta_code": self.fta_code,
            "fta_name": self.fta_name,
            "preferential_rate": self.preferential_rate,
            "mfn_rate": self.mfn_rate,
            "savings_rate": self.savings_rate,
            "savings_amount": self.savings_amount,
            "requirements": self.requirements,
            "rvc_threshold": self.rvc_threshold,
            "notes": self.notes,
        }


class FTARateService:
    """
    Service for FTA preferential rate lookups.
    
    Provides:
    - FTA eligibility checking by country + HTS
    - Preferential rate lookup
    - MFN vs FTA savings calculation
    - Certificate of origin requirement info
    """
    
    # FTA country mapping
    FTA_COUNTRIES = {
        "CA": "USMCA", "MX": "USMCA",
        "KR": "KORUS",
        "CR": "CAFTA-DR", "SV": "CAFTA-DR", "GT": "CAFTA-DR", 
        "HN": "CAFTA-DR", "NI": "CAFTA-DR", "DO": "CAFTA-DR",
        "AU": "Australia",
        "CL": "Chile",  # US-Chile FTA
        "CO": "Colombia",  # US-Colombia FTA
        "PA": "Panama",  # US-Panama FTA
        "PE": "Peru",  # US-Peru FTA
        "SG": "Singapore",  # US-Singapore FTA
        "IL": "Israel",  # US-Israel FTA
        "JO": "Jordan",  # US-Jordan FTA
        "BH": "Bahrain",  # US-Bahrain FTA
        "OM": "Oman",  # US-Oman FTA
        "MA": "Morocco",  # US-Morocco FTA
    }
    
    def check_fta_eligibility(
        self,
        country_of_origin: str,
        hts_code: str,
        entered_value: float = 0,
    ) -> FTACheckResult:
        """
        Check if HTS + country qualifies for FTA preferential treatment.
        
        Args:
            country_of_origin: 2-letter ISO country code
            hts_code: HTS code
            entered_value: Value to calculate savings
            
        Returns:
            FTACheckResult with eligibility and rate info
        """
        country = country_of_origin.upper().strip()
        hts_clean = hts_code.replace(".", "").strip()
        chapter = hts_clean[:2] if len(hts_clean) >= 2 else None
        
        if not chapter:
            return FTACheckResult(eligible=False, notes=["Invalid HTS code"])
        
        # Check if country has FTA with US
        fta_code = self.FTA_COUNTRIES.get(country)
        
        if not fta_code:
            # Check GSP eligibility
            return self._check_gsp_eligibility(country, hts_code, entered_value)
        
        # Check if HTS is excluded from this FTA
        exclusions = FTA_EXCLUSIONS.get(fta_code, {})
        
        if chapter in exclusions.get("excluded_chapters", []):
            return FTACheckResult(
                eligible=False,
                fta_code=fta_code,
                notes=[f"Chapter {chapter} excluded from {fta_code}"],
            )
        
        heading = hts_clean[:4] if len(hts_clean) >= 4 else ""
        if heading in exclusions.get("excluded_headings", []):
            return FTACheckResult(
                eligible=False,
                fta_code=fta_code,
                notes=[f"Heading {heading} excluded from {fta_code}"],
            )
        
        # Get preferential rate
        fta_rates = FTA_RATES.get(chapter, {})
        pref_rate = fta_rates.get(fta_code, Decimal("0"))
        
        # Get MFN rate
        mfn_rate = MFN_RATES.get(chapter, Decimal("5.0"))
        
        # Calculate savings
        savings_rate = float(mfn_rate) - float(pref_rate)
        savings_amount = (entered_value * savings_rate / 100) if entered_value > 0 else None
        
        # Special rules check
        special_rules = exclusions.get("special_rules", [])
        notes = []
        if chapter in special_rules:
            notes.append(f"Chapter {chapter} has special rules of origin under {fta_code}")
            if chapter in ["61", "62", "63"]:
                notes.append("Textiles: Yarn-forward rule typically applies")
        
        # Get requirements
        requirements = self._get_fta_requirements(fta_code, chapter)
        
        # RVC threshold
        rvc = self._get_rvc_threshold(fta_code, chapter)
        
        return FTACheckResult(
            eligible=True,
            fta_code=fta_code,
            fta_name=self._get_fta_name(fta_code),
            preferential_rate=float(pref_rate),
            mfn_rate=float(mfn_rate),
            savings_rate=savings_rate,
            savings_amount=savings_amount,
            requirements=requirements,
            rvc_threshold=rvc,
            notes=notes,
        )
    
    def _check_gsp_eligibility(
        self,
        country: str,
        hts_code: str,
        entered_value: float,
    ) -> FTACheckResult:
        """Check GSP (Generalized System of Preferences) eligibility."""
        hts_clean = hts_code.replace(".", "").strip()
        chapter = hts_clean[:2]
        
        if country not in GSP_COUNTRIES:
            return FTACheckResult(
                eligible=False,
                notes=[f"No FTA or GSP eligibility for {country}"],
            )
        
        if chapter in GSP_EXCLUDED_CHAPTERS:
            return FTACheckResult(
                eligible=False,
                fta_code="GSP",
                notes=[f"Chapter {chapter} excluded from GSP"],
            )
        
        mfn_rate = MFN_RATES.get(chapter, Decimal("5.0"))
        savings_amount = (entered_value * float(mfn_rate) / 100) if entered_value > 0 else None
        
        return FTACheckResult(
            eligible=True,
            fta_code="GSP",
            fta_name="Generalized System of Preferences",
            preferential_rate=0,
            mfn_rate=float(mfn_rate),
            savings_rate=float(mfn_rate),
            savings_amount=savings_amount,
            requirements=[
                "Goods must be imported directly from beneficiary country",
                "At least 35% of appraised value must be from beneficiary country",
                "Substantial transformation must occur in beneficiary country",
            ],
            notes=["GSP program status may vary - verify current eligibility"],
        )
    
    def _get_fta_requirements(self, fta_code: str, chapter: str) -> List[str]:
        """Get certificate of origin requirements for FTA."""
        base_requirements = [
            f"Valid {fta_code} Certificate of Origin required",
            "Goods must originate in FTA territory per rules of origin",
            "Direct shipment preferred (transshipment rules may apply)",
        ]
        
        if fta_code == "USMCA":
            base_requirements.append("USMCA certification by producer, exporter, or importer")
            base_requirements.append("Certification must include 9 required data elements")
            if chapter == "87":
                base_requirements.append("Automotive parts: Must meet LVC (Labor Value Content) requirements")
        elif fta_code == "KORUS":
            base_requirements.append("KORUS Form filled by exporter or producer")
        
        return base_requirements
    
    def _get_rvc_threshold(self, fta_code: str, chapter: str) -> Optional[float]:
        """Get Regional Value Content threshold."""
        rvc_thresholds = {
            "USMCA": 75.0,  # General; automotive is higher
            "KORUS": 35.0,
            "CAFTA-DR": 35.0,
            "Australia": 35.0,
        }
        
        # Special: USMCA automotive
        if fta_code == "USMCA" and chapter == "87":
            return 75.0  # Core parts requirement
        
        return rvc_thresholds.get(fta_code)
    
    def _get_fta_name(self, fta_code: str) -> str:
        """Get full FTA name."""
        names = {
            "USMCA": "United States-Mexico-Canada Agreement",
            "KORUS": "US-Korea Free Trade Agreement",
            "CAFTA-DR": "Dominican Republic-Central America FTA",
            "Australia": "US-Australia Free Trade Agreement",
            "Chile": "US-Chile Free Trade Agreement",
            "Colombia": "US-Colombia Trade Promotion Agreement",
            "Panama": "US-Panama Trade Promotion Agreement",
            "Peru": "US-Peru Trade Promotion Agreement",
            "Singapore": "US-Singapore Free Trade Agreement",
            "Israel": "US-Israel Free Trade Agreement",
            "Jordan": "US-Jordan Free Trade Agreement",
            "Bahrain": "US-Bahrain Free Trade Agreement",
            "Oman": "US-Oman Free Trade Agreement",
            "Morocco": "US-Morocco Free Trade Agreement",
            "GSP": "Generalized System of Preferences",
        }
        return names.get(fta_code, fta_code)
    
    def get_all_fta_countries(self) -> Dict[str, str]:
        """Get all countries with FTA agreements."""
        return self.FTA_COUNTRIES.copy()
    
    def compare_fta_options(
        self,
        hts_code: str,
        entered_value: float,
        countries: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Compare FTA options across multiple sourcing countries.
        
        Useful for supply chain optimization.
        """
        results = []
        
        for country in countries:
            result = self.check_fta_eligibility(country, hts_code, entered_value)
            results.append({
                "country": country,
                **result.to_dict(),
            })
        
        # Sort by savings (best first)
        results.sort(key=lambda x: x.get("savings_amount") or 0, reverse=True)
        
        return results


# Singleton
fta_rate_service = FTARateService()
