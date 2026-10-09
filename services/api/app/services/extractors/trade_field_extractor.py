"""
Regex-based Trade Document Field Extractor.

Extracts common trade document fields using pattern matching,
no LLM required. Acts as a reliable fallback when OpenAI is
unavailable, and provides fast extraction for the "document → spreadsheet" feature.

Extracted fields include:
- Bill of Lading numbers (Master BL, House BL)
- Container numbers (ISO 6346 format)
- Invoice numbers and amounts
- HTS/HS codes
- Party names (shipper, consignee, notify)
- Dates (ETD, ETA, filing dates)
- Weights and measurements
- Port information
- Entry numbers
"""

import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeFieldExtractor:
    """Extract structured fields from trade document text using regex patterns."""

    # Standard BL patterns: carrier prefix + digits, often with dashes
    BL_PATTERNS = [
        r'\b(MAEU|CMDU|OOLU|HLCU|COSU|EGLV|MSCU|MEDU|HDMU|YMLU|ONEY|APLU|SUDU)[A-Z]?\d{6,12}\b',
        r'\bM(?:ASTER\s*)?B/?L\s*(?:#|NO\.?|NUMBER)?\s*[:=]?\s*([A-Z0-9][\w\-]{5,20})',
        r'\bH(?:OUSE\s*)?B/?L\s*(?:#|NO\.?|NUMBER)?\s*[:=]?\s*([A-Z0-9][\w\-]{5,20})',
        r'\bBILL\s+OF\s+LADING\s*(?:#|NO\.?|NUMBER)?\s*[:=]?\s*([A-Z0-9][\w\-]{5,20})',
        r'\bB/?L\s*(?:#|NO\.?|NUMBER)?\s*[:=]?\s*([A-Z0-9][\w\-]{5,20})',
    ]

    # ISO 6346 container number: 4 letters + 7 digits
    CONTAINER_PATTERN = r'\b([A-Z]{4}\d{7})\b'

    # HTS code patterns: 4-10 digit customs codes with dots
    HTS_PATTERNS = [
        r'\b(\d{4}\.\d{2}\.\d{2,4})\b',  # 8471.30.0100
        r'\b(\d{4}\.\d{2})\b',  # 8471.30
        r'\bHTS\s*(?:#|NO\.?|CODE)?\s*[:=]?\s*(\d{4}[\.\d]{0,10})',
        r'\bHS\s*(?:#|NO\.?|CODE)?\s*[:=]?\s*(\d{4}[\.\d]{0,10})',
        r'\bTARIFF\s*(?:#|NO\.?|CODE)?\s*[:=]?\s*(\d{4}[\.\d]{0,10})',
    ]

    # Invoice patterns
    INVOICE_PATTERNS = [
        r'\bINV(?:OICE)?\s*(?:#|NO\.?|NUMBER)?\s*[:=]?\s*([A-Z0-9][\w\-]{2,20})',
        r'\bINVOICE\s+NUMBER\s*[:=]?\s*([A-Z0-9][\w\-]{2,20})',
    ]

    # Currency amount patterns
    AMOUNT_PATTERNS = [
        r'\$\s*([\d,]+\.?\d{0,2})',
        r'USD\s*([\d,]+\.?\d{0,2})',
        r'(?:TOTAL|AMOUNT|VALUE|PRICE|CIF|FOB)\s*[:=]?\s*\$?\s*([\d,]+\.?\d{0,2})',
    ]

    # Entry number patterns (CBP format: XXX-NNNNNNN-N)
    ENTRY_PATTERNS = [
        r'\b(\d{3}-\d{7}-\d)\b',
        r'\bENTRY\s*(?:#|NO\.?|NUMBER)?\s*[:=]?\s*([A-Z0-9][\w\-]{8,15})',
    ]

    # Port codes/names
    PORT_PATTERNS = [
        r'\bPORT\s+OF\s+(ENTRY|LOADING|DISCHARGE|UNLADING)\s*[:=]?\s*([A-Z][A-Za-z\s]{2,30})',
        r'\bPORT\s+CODE\s*[:=]?\s*(\d{4})',
    ]

    # Weight patterns
    WEIGHT_PATTERNS = [
        r'([\d,]+\.?\d{0,3})\s*(?:KG|KGS|KILOS?|KILOGRAMS?)',
        r'([\d,]+\.?\d{0,3})\s*(?:LBS?|POUNDS?)',
        r'\bGROSS\s*(?:WEIGHT|WT\.?)\s*[:=]?\s*([\d,]+\.?\d{0,3})',
        r'\bNET\s*(?:WEIGHT|WT\.?)\s*[:=]?\s*([\d,]+\.?\d{0,3})',
    ]

    # Date patterns
    DATE_PATTERNS = [
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
        r'(\d{4}[/\-]\d{1,2}[/\-]\d{1,2})',
        r'((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{1,2},?\s+\d{4})',
    ]

    # Party/name patterns
    PARTY_PATTERNS = {
        'shipper': [
            r'SHIPPER\s*[:=]?\s*([A-Z][A-Za-z\s&,\.]{3,50})',
            r'EXPORTER\s*[:=]?\s*([A-Z][A-Za-z\s&,\.]{3,50})',
        ],
        'consignee': [
            r'CONSIGNEE\s*[:=]?\s*([A-Z][A-Za-z\s&,\.]{3,50})',
            r'IMPORTER\s*[:=]?\s*([A-Z][A-Za-z\s&,\.]{3,50})',
        ],
        'notify_party': [
            r'NOTIFY\s*(?:PARTY)?\s*[:=]?\s*([A-Z][A-Za-z\s&,\.]{3,50})',
        ],
    }

    # Country of origin
    COUNTRY_PATTERNS = [
        r'\bCOUNTRY\s+OF\s+ORIGIN\s*[:=]?\s*([A-Z][A-Za-z\s]{2,30})',
        r'\bORIGIN\s*[:=]?\s*([A-Z]{2,3}(?:\s*-\s*[A-Za-z\s]{2,30})?)',
        r'\bMADE\s+IN\s+([A-Z][A-Za-z\s]{2,20})',
    ]

    # Booking number
    BOOKING_PATTERNS = [
        r'\bBOOKING\s*(?:#|NO\.?|NUMBER|REF)?\s*[:=]?\s*([A-Z0-9][\w\-]{4,20})',
    ]

    # ISF Bond information
    BOND_PATTERNS = [
        r'\bBOND\s*(?:#|NO\.?|NUMBER|TYPE)?\s*[:=]?\s*([A-Z0-9][\w\-]{2,20})',
        r'\bSURETY\s*(?:CODE)?\s*[:=]?\s*(\d{3,6})',
    ]

    @classmethod
    def extract_fields(cls, text: str, filename: str = None) -> Dict[str, Any]:
        """
        Extract all recognizable trade document fields from text.
        
        Returns a structured dict with:
        - status: "success" or "error"
        - document_metadata: detected document type and confidence
        - parties: shipper, consignee, notify_party
        - shipment: BL numbers, containers, booking
        - cargo: items with HTS codes
        - financials: invoice, amounts
        - customs_entry: entry numbers
        """
        if not text or len(text.strip()) < 20:
            return {"status": "error", "error": "Text too short"}

        text_upper = text.upper()
        results = {
            "status": "success",
            "extraction_method": "regex",
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "source_filename": filename,
        }

        # 1. Detect document type from filename and content
        results["document_metadata"] = cls._detect_document_type(text_upper, filename)

        # 2. Extract BL numbers
        master_bl, house_bl, other_bls = cls._extract_bl_numbers(text_upper)
        results["shipment"] = {
            "master_bl_number": master_bl,
            "house_bl_number": house_bl,
        }

        # 3. Container numbers
        containers = cls._extract_containers(text_upper)
        results["shipment"]["containers"] = [
            {"number": c} for c in containers
        ]

        # 4. Booking number
        booking = cls._extract_first_match(text_upper, cls.BOOKING_PATTERNS)
        results["shipment"]["booking_number"] = booking

        # 5. Parties
        results["parties"] = {}
        for role, patterns in cls.PARTY_PATTERNS.items():
            name = cls._extract_first_match(text, patterns)
            if name:
                results["parties"][role] = {"name": name.strip()}

        # 6. HTS codes and cargo
        hts_codes = cls._extract_hts_codes(text_upper)
        results["cargo"] = {
            "items": [
                {
                    "description": f"Item with HTS {code}",
                    "hts_code_10_digit": code,
                    "hs_code": code[:7] if len(code) > 7 else code,
                }
                for code in hts_codes
            ]
        }

        # 7. Invoice and financials
        invoice_num = cls._extract_first_match(text_upper, cls.INVOICE_PATTERNS)
        amounts = cls._extract_amounts(text_upper)
        results["financials"] = {
            "invoice_number": invoice_num,
            "currency": "USD",
        }
        if amounts:
            results["financials"]["total_invoice_value"] = max(amounts)

        # 8. Entry number
        entry_num = cls._extract_first_match(text_upper, cls.ENTRY_PATTERNS)
        results["customs_entry"] = {
            "entry_number": entry_num,
        }

        # 9. Dates
        dates = cls._extract_dates(text_upper)
        results["deadlines_and_risks"] = {}
        if dates:
            results["deadlines_and_risks"]["extracted_dates"] = dates[:5]

        # 10. Weights
        weights = cls._extract_weights(text_upper)
        if weights:
            results["cargo"]["gross_weight_kg"] = weights[0]

        # 11. Country of origin
        origin = cls._extract_first_match(text_upper, cls.COUNTRY_PATTERNS)
        if origin:
            for item in results["cargo"].get("items", []):
                item["country_of_origin"] = origin.strip()

        # 12. Port info
        ports = cls._extract_ports(text_upper)
        results["shipment"].update(ports)

        return results

    @classmethod
    def _detect_document_type(cls, text_upper: str, filename: str = None) -> Dict:
        """Detect document type from content and filename."""
        type_scores = {
            "Bill of Lading": 0,
            "Commercial Invoice": 0,
            "Packing List": 0,
            "Arrival Notice": 0,
            "ISF Filing": 0,
            "Customs Entry": 0,
            "Certificate of Origin": 0,
        }

        # Filename hints (strongest signal)
        fn = (filename or "").lower()
        if "bl" in fn or "bill" in fn or "lading" in fn:
            if "master" in fn:
                type_scores["Bill of Lading"] += 5
            elif "house" in fn:
                type_scores["Bill of Lading"] += 5
            else:
                type_scores["Bill of Lading"] += 4
        if "invoice" in fn or "commercial" in fn:
            type_scores["Commercial Invoice"] += 5
        if "packing" in fn or "pack_list" in fn:
            type_scores["Packing List"] += 5
        if "arrival" in fn or "notice" in fn:
            type_scores["Arrival Notice"] += 4
        if "isf" in fn:
            type_scores["ISF Filing"] += 5
        if "entry" in fn or "customs" in fn:
            type_scores["Customs Entry"] += 4
        if "origin" in fn or "certificate" in fn:
            type_scores["Certificate of Origin"] += 4

        # Content keywords
        keyword_map = {
            "Bill of Lading": ["BILL OF LADING", "B/L NO", "BL NUMBER", "SHIPPER", "CONSIGNEE", "NOTIFY PARTY", "PORT OF LOADING"],
            "Commercial Invoice": ["COMMERCIAL INVOICE", "INVOICE NO", "UNIT PRICE", "TOTAL AMOUNT", "TERMS OF SALE"],
            "Packing List": ["PACKING LIST", "CARTON", "GROSS WEIGHT", "NET WEIGHT", "CBM", "DIMENSIONS"],
            "Arrival Notice": ["ARRIVAL NOTICE", "ESTIMATED ARRIVAL", "LAST FREE DAY", "DEMURRAGE", "DETENTION"],
            "ISF Filing": ["ISF", "IMPORTER SECURITY FILING", "10+2", "MANUFACTURER", "SELLER"],
            "Customs Entry": ["ENTRY NO", "ENTRY TYPE", "PORT OF ENTRY", "DUTY", "TARIFF", "CBP"],
            "Certificate of Origin": ["CERTIFICATE OF ORIGIN", "COUNTRY OF ORIGIN", "MANUFACTURER"],
        }

        for doc_type, keywords in keyword_map.items():
            for kw in keywords:
                if kw in text_upper:
                    type_scores[doc_type] += 1

        best_type = max(type_scores, key=type_scores.get)
        best_score = type_scores[best_type]
        confidence = min(0.95, max(0.3, best_score / 8.0))

        return {
            "document_type": best_type if best_score > 0 else "Unknown",
            "confidence_score": round(confidence, 2),
        }

    @classmethod
    def _extract_bl_numbers(cls, text_upper: str):
        """Extract master and house BL numbers."""
        master_bl = None
        house_bl = None
        other_bls = []

        # Try carrier-prefix patterns first (most reliable)
        carrier_bls = re.findall(cls.BL_PATTERNS[0], text_upper)
        if carrier_bls:
            full_matches = re.findall(r'\b(' + cls.BL_PATTERNS[0].strip(r'\b') + r')\b', text_upper)
            for bl in full_matches:
                if isinstance(bl, tuple):
                    bl = bl[0]
                other_bls.append(bl)

        # Try labeled patterns
        for pattern in cls.BL_PATTERNS[1:]:
            match = re.search(pattern, text_upper, re.IGNORECASE)
            if match:
                bl_num = match.group(1) if match.lastindex else match.group(0)
                if 'MASTER' in pattern.upper() or 'M' == pattern[0]:
                    master_bl = master_bl or bl_num
                elif 'HOUSE' in pattern.upper() or 'H' == pattern[0]:
                    house_bl = house_bl or bl_num
                else:
                    other_bls.append(bl_num)

        # If we found carrier-prefix BLs but no master, use first one
        if not master_bl and other_bls:
            master_bl = other_bls[0]

        return master_bl, house_bl, other_bls

    @classmethod
    def _extract_containers(cls, text_upper: str) -> List[str]:
        """Extract ISO 6346 container numbers."""
        return list(set(re.findall(cls.CONTAINER_PATTERN, text_upper)))

    @classmethod
    def _extract_hts_codes(cls, text_upper: str) -> List[str]:
        """Extract HTS/HS tariff codes."""
        codes = set()
        for pattern in cls.HTS_PATTERNS:
            for match in re.finditer(pattern, text_upper):
                code = match.group(1) if match.lastindex else match.group(0)
                # Filter out dates and other false positives
                if not re.match(r'\d{4}[/\-]\d{2}[/\-]\d{2}', code):
                    codes.add(code)
        return list(codes)

    @classmethod
    def _extract_amounts(cls, text_upper: str) -> List[float]:
        """Extract monetary amounts."""
        amounts = []
        for pattern in cls.AMOUNT_PATTERNS:
            for match in re.finditer(pattern, text_upper, re.IGNORECASE):
                try:
                    val = match.group(1).replace(',', '')
                    amounts.append(float(val))
                except (ValueError, IndexError):
                    pass
        return sorted(set(amounts))

    @classmethod
    def _extract_dates(cls, text_upper: str) -> List[str]:
        """Extract date strings."""
        dates = set()
        for pattern in cls.DATE_PATTERNS:
            for match in re.finditer(pattern, text_upper, re.IGNORECASE):
                dates.add(match.group(1))
        return list(dates)

    @classmethod
    def _extract_weights(cls, text_upper: str) -> List[float]:
        """Extract weight values (convert to kg)."""
        weights = []
        for pattern in cls.WEIGHT_PATTERNS:
            for match in re.finditer(pattern, text_upper, re.IGNORECASE):
                try:
                    val = match.group(1).replace(',', '')
                    weight = float(val)
                    # Convert lbs to kg if needed
                    if 'LB' in pattern or 'POUND' in pattern:
                        weight = weight * 0.453592
                    weights.append(weight)
                except (ValueError, IndexError):
                    pass
        return weights

    @classmethod
    def _extract_ports(cls, text_upper: str) -> Dict[str, str]:
        """Extract port information."""
        ports = {}
        for pattern in cls.PORT_PATTERNS:
            for match in re.finditer(pattern, text_upper, re.IGNORECASE):
                if match.lastindex and match.lastindex >= 2:
                    port_type = match.group(1).lower().replace(" ", "_")
                    ports[f"port_of_{port_type}"] = match.group(2).strip()
                elif match.lastindex:
                    code = match.group(1)
                    ports["port_code"] = code
        return ports

    @classmethod
    def _extract_first_match(cls, text: str, patterns: list) -> Optional[str]:
        """Return first match from a list of patterns."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if match.lastindex else match.group(0)
        return None
