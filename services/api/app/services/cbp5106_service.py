"""
CBP Form 5106 Service  (Task 2.2)

Manages CBP Form 5106 (Importer ID Number Application) for first-time
importers.  CBP requires this to assign an IOR (Importer of Record)
number before any formal entry can be filed.

Reference: CBP Publication No. 0000-0528 (Form 5106)

The service handles:
  - Validation of all required 5106 fields
  - Generation of ACS/ACE-formatted 5106 data packet
  - Tracking of submission and approval status
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# CBP-required fields for Form 5106
REQUIRED_FIELDS_INDIVIDUAL = [
    "last_name", "first_name", "ssn_or_tin", "address_line1",
    "city", "state", "zip_code", "country_code",
]

REQUIRED_FIELDS_BUSINESS = [
    "legal_name", "ein", "address_line1",
    "city", "state", "zip_code", "country_code",
    "contact_name", "contact_phone",
]

# Entity type codes per CBP spec
ENTITY_TYPES = {
    "individual":   "1",
    "corporation":  "2",
    "partnership":  "3",
    "llc":          "4",
    "government":   "5",
    "other":        "9",
}


class CBP5106Service:
    """
    Validates and builds CBP Form 5106 data for IOR registration.

    This service is intentionally stateless — it operates on plain
    dicts so it's trivially testable without a DB session.
    """

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate 5106 data.  Returns a list of error strings.
        Empty list means valid.
        """
        errors = []
        entity_type = data.get("entity_type", "corporation")

        if entity_type == "individual":
            required = REQUIRED_FIELDS_INDIVIDUAL
        else:
            required = REQUIRED_FIELDS_BUSINESS

        for field in required:
            if not data.get(field):
                errors.append(f"Required field missing: {field}")

        # Validate EIN format (XX-XXXXXXX) for businesses
        if entity_type != "individual":
            ein = data.get("ein", "")
            if ein and not self._validate_ein(ein):
                errors.append(f"Invalid EIN format '{ein}'. Expected: XX-XXXXXXX")

        # Validate SSN format for individuals
        if entity_type == "individual":
            ssn = data.get("ssn_or_tin", "")
            if ssn and not self._validate_ssn(ssn):
                errors.append(f"Invalid SSN format '{ssn}'. Expected: XXX-XX-XXXX")

        # US ZIP code
        zip_code = data.get("zip_code", "")
        if zip_code and data.get("country_code", "US") == "US":
            if not re.match(r"^\d{5}(-\d{4})?$", zip_code):
                errors.append(f"Invalid US ZIP code: {zip_code}")

        return errors

    def is_valid(self, data: Dict[str, Any]) -> bool:
        """Return True if the 5106 data passes all validations."""
        return len(self.validate(data)) == 0

    # ------------------------------------------------------------------
    # Data construction
    # ------------------------------------------------------------------

    def build_5106_packet(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a normalised CBP 5106 data packet.

        Raises ValueError if validation fails.
        """
        errors = self.validate(data)
        if errors:
            raise ValueError(f"5106 validation failed: {'; '.join(errors)}")

        entity_type = data.get("entity_type", "corporation")
        entity_code = ENTITY_TYPES.get(entity_type, "9")

        packet = {
            "form_type": "5106",
            "entity_type_code": entity_code,
            "entity_type": entity_type,
            # Business identity
            "legal_name": data.get("legal_name") or f"{data.get('last_name')}, {data.get('first_name')}",
            "doing_business_as": data.get("doing_business_as"),
            "ein": data.get("ein"),
            "ssn_or_tin": data.get("ssn_or_tin"),  # Individual only
            # Address (CBP uses structured address)
            "address_line1": data.get("address_line1"),
            "address_line2": data.get("address_line2"),
            "city": data.get("city"),
            "state": data.get("state"),
            "zip_code": data.get("zip_code"),
            "country_code": data.get("country_code", "US"),
            # Contact
            "contact_name": data.get("contact_name"),
            "contact_phone": data.get("contact_phone"),
            "contact_email": data.get("contact_email"),
            # Importer data
            "business_type": data.get("business_type"),
            "import_purpose": data.get("import_purpose"),
            "is_broker": data.get("is_broker", False),
            # Submission metadata
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_cbp_review",
        }
        return {k: v for k, v in packet.items() if v is not None}

    def generate_ior_number(self, ein: str) -> str:
        """
        Derive a provisional IOR number from an EIN.

        CBP uses EIN-based IOR numbers for corporations.
        Format: EIN without dash (9 digits)
        """
        return ein.replace("-", "").strip()

    # ------------------------------------------------------------------
    # Private validators
    # ------------------------------------------------------------------

    def _validate_ein(self, ein: str) -> bool:
        """Validate EIN format XX-XXXXXXX."""
        return bool(re.match(r"^\d{2}-\d{7}$", ein.strip()))

    def _validate_ssn(self, ssn: str) -> bool:
        """Validate SSN format XXX-XX-XXXX."""
        return bool(re.match(r"^\d{3}-\d{2}-\d{4}$", ssn.strip()))
