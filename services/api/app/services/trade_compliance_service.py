"""
Trade Compliance Service - AD/CVD, Section 301/232, FTA Eligibility

Migrated from G.A.T.E.S. reference project with adaptations for doc-ingestion platform.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ANTIDUMPING / COUNTERVAILING DUTY (AD/CVD) DATABASE
# Source: USITC AD/CVD Orders - Common products subject to duties
# ============================================================================

ADCVD_ORDERS = [
    # Steel Products
    {"id": "A-570-967", "country": "China", "product": "Steel Wire Garment Hangers", "hts_prefix": "7326.20", "ad_rate": 187.25, "cvd_rate": 0, "effective_date": "2008-07-30"},
    {"id": "A-570-904", "country": "China", "product": "Circular Welded Carbon Quality Steel Pipe", "hts_prefix": "7306.30", "ad_rate": 69.20, "cvd_rate": 29.57, "effective_date": "2008-07-22"},
    {"id": "A-570-909", "country": "China", "product": "Circular Welded Carbon Steel Pipes and Tubes", "hts_prefix": "7306", "ad_rate": 85.55, "cvd_rate": 615.92, "effective_date": "2008-06-12"},
    {"id": "A-570-910", "country": "China", "product": "Light-Walled Rectangular Pipe and Tube", "hts_prefix": "7306.61", "ad_rate": 249.12, "cvd_rate": 32.25, "effective_date": "2008-08-05"},
    {"id": "A-570-601", "country": "China", "product": "Heavy Forged Hand Tools", "hts_prefix": "8205", "ad_rate": 45.42, "cvd_rate": 0, "effective_date": "1991-02-14"},
    {"id": "A-570-831", "country": "China", "product": "Cut-to-Length Carbon Steel Plate", "hts_prefix": "7208.51", "ad_rate": 128.59, "cvd_rate": 251.00, "effective_date": "2017-04-05"},
    
    # Aluminum Products
    {"id": "A-570-053", "country": "China", "product": "Aluminum Extrusions", "hts_prefix": "7604", "ad_rate": 374.15, "cvd_rate": 351.44, "effective_date": "2011-05-26"},
    {"id": "A-570-967-AL", "country": "China", "product": "Aluminum Foil", "hts_prefix": "7607", "ad_rate": 106.09, "cvd_rate": 128.46, "effective_date": "2018-03-15"},
    
    # Solar Products
    {"id": "A-570-979", "country": "China", "product": "Crystalline Silicon Photovoltaic Cells", "hts_prefix": "8541.40", "ad_rate": 238.95, "cvd_rate": 15.97, "effective_date": "2012-12-07"},
    
    # Tires
    {"id": "A-570-016", "country": "China", "product": "Passenger Vehicle and Light Truck Tires", "hts_prefix": "4011.10", "ad_rate": 87.99, "cvd_rate": 38.61, "effective_date": "2015-08-11"},
    {"id": "A-570-017", "country": "China", "product": "Truck and Bus Tires", "hts_prefix": "4011.20", "ad_rate": 22.57, "cvd_rate": 42.16, "effective_date": "2017-03-01"},
    
    # Wood Products
    {"id": "A-122-857", "country": "Canada", "product": "Softwood Lumber", "hts_prefix": "4407.10", "ad_rate": 8.59, "cvd_rate": 11.64, "effective_date": "2020-12-01"},
    
    # Chemicals
    {"id": "A-570-898", "country": "China", "product": "Sodium Hexametaphosphate", "hts_prefix": "2835.31", "ad_rate": 187.22, "cvd_rate": 0, "effective_date": "2008-09-11"},
    {"id": "A-570-836", "country": "China", "product": "Glycine", "hts_prefix": "2922.49", "ad_rate": 453.00, "cvd_rate": 0, "effective_date": "2004-02-25"},
    
    # Furniture/Home Goods
    {"id": "A-570-890", "country": "China", "product": "Wooden Bedroom Furniture", "hts_prefix": "9403.50", "ad_rate": 216.01, "cvd_rate": 0, "effective_date": "2005-01-04"},
    {"id": "A-570-888", "country": "China", "product": "Uncovered Innerspring Units", "hts_prefix": "9404.10", "ad_rate": 234.51, "cvd_rate": 0, "effective_date": "2009-02-19"},
    
    # Electronics
    {"id": "A-570-863", "country": "China", "product": "Polyethylene Terephthalate Film", "hts_prefix": "3920.62", "ad_rate": 4.80, "cvd_rate": 2.17, "effective_date": "2008-11-06"},
]

# ============================================================================
# SECTION 301 TARIFFS (China)
# ============================================================================

SECTION_301_LISTS = {
    "list_1": {
        "rate": 25.0,
        "effective_date": "2018-07-06",
        "description": "$34 billion - Industrial machinery, electronics",
        "hts_prefixes": ["8471", "8473", "8517", "8525", "8536", "8541", "8542", "8708", "9031"]
    },
    "list_2": {
        "rate": 25.0,
        "effective_date": "2018-08-23",
        "description": "$16 billion - Semiconductors, chemicals, plastics",
        "hts_prefixes": ["2710", "2711", "3901", "3902", "3903", "3904", "3907", "3920", "8479", "8483"]
    },
    "list_3": {
        "rate": 25.0,
        "effective_date": "2019-05-10",
        "description": "$200 billion - Consumer goods, intermediate goods",
        "hts_prefixes": ["39", "40", "42", "44", "61", "62", "63", "64", "65", "69", "70", "73", "76", "83", "84", "85", "87", "90", "94", "95", "96"]
    },
    "list_4a": {
        "rate": 7.5,
        "effective_date": "2020-02-14",
        "description": "$120 billion - Additional consumer products (reduced rate)",
        "hts_prefixes": ["42", "61", "62", "63", "64", "65", "66", "67"]
    }
}

# ============================================================================
# SECTION 232 TARIFFS (Steel & Aluminum)
# ============================================================================

SECTION_232_STEEL = {
    "rate": 25.0,
    "effective_date": "2018-03-23",
    "description": "Steel imports - National security tariff",
    "hts_chapters": ["72", "73"],
    "exempted_countries": ["Canada", "Mexico", "Australia", "Argentina", "Brazil", "South Korea"]
}

SECTION_232_ALUMINUM = {
    "rate": 10.0,
    "effective_date": "2018-03-23",
    "description": "Aluminum imports - National security tariff",
    "hts_chapters": ["76"],
    "exempted_countries": ["Canada", "Mexico", "Australia", "Argentina"]
}

# ============================================================================
# FREE TRADE AGREEMENTS
# ============================================================================

FTA_AGREEMENTS = {
    "USMCA": {
        "name": "United States-Mexico-Canada Agreement",
        "countries": ["Canada", "Mexico", "CA", "MX"],
        "effective_date": "2020-07-01",
        "general_rules": [
            "Goods must be wholly obtained or produced entirely in the territory",
            "Non-originating materials must undergo substantial transformation",
            "Must meet product-specific rules of origin",
            "Regional Value Content (RVC) thresholds may apply"
        ],
        "rvc_thresholds": {"transaction_value": 75.0, "net_cost": 70.0},
        "automotive_requirements": {
            "vehicle_rvc": 75.0,
            "core_parts": 75.0,
            "principal_parts": 70.0,
            "complementary_parts": 65.0,
            "steel_aluminum_requirement": 70.0,
            "labor_value_content": 40.0
        }
    },
    "CAFTA-DR": {
        "name": "Dominican Republic-Central America FTA",
        "countries": ["Costa Rica", "El Salvador", "Guatemala", "Honduras", "Nicaragua", "Dominican Republic", "CR", "SV", "GT", "HN", "NI", "DO"],
        "effective_date": "2006-03-01",
        "general_rules": [
            "Goods must be wholly obtained in FTA territory",
            "Tariff shift rules apply to non-originating materials",
            "Regional Value Content of 35% minimum (build-up) or 45% (build-down)"
        ],
        "rvc_thresholds": {"build_up": 35.0, "build_down": 45.0}
    },
    "Korea": {
        "name": "US-Korea Free Trade Agreement (KORUS)",
        "countries": ["South Korea", "Korea", "KR"],
        "effective_date": "2012-03-15",
        "general_rules": [
            "Goods wholly obtained or produced in Korea or US",
            "Tariff shift plus RVC requirements for many products"
        ],
        "rvc_thresholds": {"general": 35.0}
    },
    "Australia": {
        "name": "US-Australia Free Trade Agreement",
        "countries": ["Australia", "AU"],
        "effective_date": "2005-01-01",
        "general_rules": [
            "Goods wholly obtained or produced in territory",
            "RVC requirement of 35% minimum"
        ],
        "rvc_thresholds": {"general": 35.0}
    }
}


class TradeComplianceService:
    """Service for trade compliance screening: AD/CVD, Section 301/232, FTA eligibility."""

    @staticmethod
    def screen_adcvd(hts_code: str, country_of_origin: str) -> List[Dict[str, Any]]:
        """Screen item for AD/CVD duties."""
        matches = []
        hts_clean = hts_code.replace(".", "").replace(" ", "")[:6]
        
        for order in ADCVD_ORDERS:
            if order["country"].lower() not in country_of_origin.lower():
                continue
            
            prefix = order["hts_prefix"].replace(".", "")
            if hts_clean.startswith(prefix) or prefix.startswith(hts_clean[:4]):
                matches.append({
                    "order_id": order["id"],
                    "country": order["country"],
                    "product": order["product"],
                    "ad_rate": order["ad_rate"],
                    "cvd_rate": order["cvd_rate"],
                    "combined_rate": order["ad_rate"] + order["cvd_rate"],
                    "effective_date": order["effective_date"],
                    "match_type": "prefix_match",
                    "severity": "high" if order["ad_rate"] + order["cvd_rate"] > 100 else "medium"
                })
        
        return matches

    @staticmethod
    def screen_section_301(hts_code: str, country_of_origin: str) -> Dict[str, Any]:
        """Screen item for Section 301 tariffs (China)."""
        result = {
            "subject_to_301": False,
            "lists": [],
            "total_rate": 0.0,
            "country": country_of_origin
        }
        
        china_indicators = ["china", "cn", "prc", "people's republic"]
        if not any(ind in country_of_origin.lower() for ind in china_indicators):
            return result
        
        hts_clean = hts_code.replace(".", "").replace(" ", "")
        hts_chapter = hts_clean[:2]
        hts_4digit = hts_clean[:4]
        
        for list_name, list_data in SECTION_301_LISTS.items():
            for prefix in list_data["hts_prefixes"]:
                if hts_clean.startswith(prefix) or hts_chapter == prefix or hts_4digit.startswith(prefix):
                    result["subject_to_301"] = True
                    result["lists"].append({
                        "list": list_name,
                        "rate": list_data["rate"],
                        "effective_date": list_data["effective_date"],
                        "description": list_data["description"]
                    })
                    break
        
        if result["lists"]:
            result["total_rate"] = max(l["rate"] for l in result["lists"])
        
        return result

    @staticmethod
    def screen_section_232(hts_code: str, country_of_origin: str) -> Dict[str, Any]:
        """Screen item for Section 232 tariffs (Steel/Aluminum)."""
        result = {
            "subject_to_232": False,
            "product_type": None,
            "rate": 0.0,
            "exempted": False,
            "exemption_reason": None
        }
        
        hts_chapter = hts_code.replace(".", "")[:2]
        
        # Check steel
        if hts_chapter in SECTION_232_STEEL["hts_chapters"]:
            result["subject_to_232"] = True
            result["product_type"] = "steel"
            result["rate"] = SECTION_232_STEEL["rate"]
            
            for exempted in SECTION_232_STEEL["exempted_countries"]:
                if exempted.lower() in country_of_origin.lower():
                    result["exempted"] = True
                    result["exemption_reason"] = f"{country_of_origin} exempted from steel tariffs"
                    result["rate"] = 0.0
                    break
        
        # Check aluminum
        elif hts_chapter in SECTION_232_ALUMINUM["hts_chapters"]:
            result["subject_to_232"] = True
            result["product_type"] = "aluminum"
            result["rate"] = SECTION_232_ALUMINUM["rate"]
            
            for exempted in SECTION_232_ALUMINUM["exempted_countries"]:
                if exempted.lower() in country_of_origin.lower():
                    result["exempted"] = True
                    result["exemption_reason"] = f"{country_of_origin} exempted from aluminum tariffs"
                    result["rate"] = 0.0
                    break
        
        return result

    @staticmethod
    def check_fta_eligibility(country_of_origin: str, hts_code: str = None) -> Dict[str, Any]:
        """Check if country qualifies for FTA preferential treatment."""
        result = {
            "eligible_ftas": [],
            "has_fta": False,
            "best_option": None,
            "requirements": []
        }
        
        for fta_code, fta_data in FTA_AGREEMENTS.items():
            for country in fta_data["countries"]:
                if country.lower() in country_of_origin.lower():
                    fta_info = {
                        "agreement": fta_code,
                        "name": fta_data["name"],
                        "effective_date": fta_data["effective_date"],
                        "general_rules": fta_data["general_rules"],
                        "rvc_thresholds": fta_data["rvc_thresholds"]
                    }
                    
                    if fta_code == "USMCA" and "automotive_requirements" in fta_data:
                        fta_info["automotive_requirements"] = fta_data["automotive_requirements"]
                    
                    result["eligible_ftas"].append(fta_info)
                    result["has_fta"] = True
                    break
        
        if result["eligible_ftas"]:
            result["best_option"] = result["eligible_ftas"][0]
            result["requirements"] = result["best_option"]["general_rules"]
        
        return result

    @staticmethod
    def comprehensive_duty_screening(
        hts_code: str,
        country_of_origin: str,
        entered_value: float = 0.0
    ) -> Dict[str, Any]:
        """Perform comprehensive duty screening for an item."""
        result = {
            "hts_code": hts_code,
            "country_of_origin": country_of_origin,
            "entered_value": entered_value,
            "adcvd": TradeComplianceService.screen_adcvd(hts_code, country_of_origin),
            "section_301": TradeComplianceService.screen_section_301(hts_code, country_of_origin),
            "section_232": TradeComplianceService.screen_section_232(hts_code, country_of_origin),
            "fta_eligibility": TradeComplianceService.check_fta_eligibility(country_of_origin, hts_code),
            "alerts": [],
            "estimated_additional_duties": 0.0
        }
        
        additional = 0.0
        
        # AD/CVD
        if result["adcvd"]:
            for order in result["adcvd"]:
                rate = order["combined_rate"] / 100
                additional += entered_value * rate
                result["alerts"].append({
                    "type": "adcvd",
                    "severity": order["severity"],
                    "message": f"Subject to AD/CVD Order {order['order_id']}: {order['product']} ({order['combined_rate']:.1f}%)"
                })
        
        # Section 301
        if result["section_301"]["subject_to_301"]:
            rate = result["section_301"]["total_rate"] / 100
            additional += entered_value * rate
            result["alerts"].append({
                "type": "section_301",
                "severity": "high",
                "message": f"Subject to Section 301 tariff: {result['section_301']['total_rate']}% additional duty"
            })
        
        # Section 232
        if result["section_232"]["subject_to_232"] and not result["section_232"]["exempted"]:
            rate = result["section_232"]["rate"] / 100
            additional += entered_value * rate
            result["alerts"].append({
                "type": "section_232",
                "severity": "medium",
                "message": f"Subject to Section 232 {result['section_232']['product_type']} tariff: {result['section_232']['rate']}%"
            })
        
        # FTA opportunity
        if result["fta_eligibility"]["has_fta"]:
            result["alerts"].append({
                "type": "fta_opportunity",
                "severity": "info",
                "message": f"May qualify for duty-free treatment under {result['fta_eligibility']['best_option']['agreement']}"
            })
        
        result["estimated_additional_duties"] = round(additional, 2)
        
        return result

    @staticmethod
    def calculate_liquidation_dates(entry_date: str) -> Dict[str, Any]:
        """
        Calculate liquidation window and deadlines.
        
        Per 19 USC 1504:
        - Entries liquidate within 314 days
        - Protest must be filed within 180 days of liquidation
        """
        try:
            entry_dt = datetime.strptime(entry_date[:10], "%Y-%m-%d")
        except:
            entry_dt = datetime.now()
        
        now = datetime.now()
        
        liquidation_deadline = entry_dt + timedelta(days=314)
        max_extension = entry_dt + timedelta(days=4*365)
        protest_deadline = liquidation_deadline + timedelta(days=180)
        
        days_until_liquidation = (liquidation_deadline - now).days
        days_until_protest = (protest_deadline - now).days
        
        if days_until_liquidation <= 0:
            liq_status, liq_urgency = "liquidated", "none"
        elif days_until_liquidation <= 30:
            liq_status, liq_urgency = "imminent", "critical"
        elif days_until_liquidation <= 90:
            liq_status, liq_urgency = "approaching", "high"
        elif days_until_liquidation <= 180:
            liq_status, liq_urgency = "active", "medium"
        else:
            liq_status, liq_urgency = "open", "low"
        
        return {
            "entry_date": entry_dt.strftime("%Y-%m-%d"),
            "liquidation_deadline": liquidation_deadline.strftime("%Y-%m-%d"),
            "days_until_liquidation": max(0, days_until_liquidation),
            "liquidation_status": liq_status,
            "liquidation_urgency": liq_urgency,
            "protest_deadline": protest_deadline.strftime("%Y-%m-%d"),
            "days_until_protest_deadline": max(0, days_until_protest),
            "max_extension_date": max_extension.strftime("%Y-%m-%d"),
            "is_liquidated": days_until_liquidation <= 0,
            "can_protest": days_until_protest > 0
        }


# Singleton instance for convenience
trade_compliance_service = TradeComplianceService()
