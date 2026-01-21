"""Service for validating normalized metadata."""
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class ValidationService:
    """Service for validating normalized metadata fields."""

    # Validation rules per field
    VALIDATION_RULES = {
        "title": {"required": False, "max_length": 1000, "type": str},
        "author": {"required": False, "max_length": 500, "type": str},
        "language": {"required": False, "pattern": r"^[a-z]{2}(-[A-Z]{2})?$", "type": str},
        "page_count": {"required": False, "type": int, "min": 0, "max": 100000},
        "document_type": {"required": False, "max_length": 100, "type": str},
        "date": {"required": False, "type": str},
        "tags": {"required": False, "type": list},
        "content_hash": {"required": False, "pattern": r"^[a-f0-9]{64}$", "type": str},
    }

    @staticmethod
    async def validate_fields(data: Dict) -> Tuple[bool, List[Dict]]:
        """
        Validate normalized metadata fields.

        Args:
            data: Dictionary of normalized metadata

        Returns:
            Tuple of (is_valid, validation_errors)
        """
        errors = []

        for field, value in data.items():
            if field not in ValidationService.VALIDATION_RULES:
                continue

            rule = ValidationService.VALIDATION_RULES[field]

            # Check required
            if rule.get("required") and value is None:
                errors.append({
                    "field": field,
                    "reason": f"{field} is required",
                    "type": "required",
                })
                continue

            if value is None:
                continue

            # Check type
            expected_type = rule.get("type")
            if expected_type and not isinstance(value, expected_type):
                errors.append({
                    "field": field,
                    "reason": f"{field} must be {expected_type.__name__}",
                    "type": "type_mismatch",
                })
                continue

            # Check max_length
            if "max_length" in rule and isinstance(value, str):
                if len(value) > rule["max_length"]:
                    errors.append({
                        "field": field,
                        "reason": f"{field} exceeds max length {rule['max_length']}",
                        "type": "max_length",
                    })

            # Check min/max for numbers
            if isinstance(value, (int, float)):
                if "min" in rule and value < rule["min"]:
                    errors.append({
                        "field": field,
                        "reason": f"{field} is below minimum {rule['min']}",
                        "type": "min",
                    })
                if "max" in rule and value > rule["max"]:
                    errors.append({
                        "field": field,
                        "reason": f"{field} exceeds maximum {rule['max']}",
                        "type": "max",
                    })

        is_valid = len(errors) == 0
        logger.info(f"Validation result: valid={is_valid}, errors={len(errors)}")

        return is_valid, errors

    @staticmethod
    async def validate_required_fields(data: Dict) -> Tuple[bool, List[str]]:
        """Check that all required fields are present."""
        missing_fields = []

        for field, rule in ValidationService.VALIDATION_RULES.items():
            if rule.get("required") and not data.get(field):
                missing_fields.append(field)

        return len(missing_fields) == 0, missing_fields
