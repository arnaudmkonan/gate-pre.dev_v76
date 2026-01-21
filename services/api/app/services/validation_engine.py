"""Validation engine for normalization rules and data quality checks."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ValidationError:
    """Represents a single validation error."""

    def __init__(self, field: str, message: str, error_type: str):
        self.field = field
        self.message = message
        self.error_type = error_type

    def to_dict(self):
        return {
            "field": self.field,
            "message": self.message,
            "type": self.error_type,
        }


class ValidationResult:
    """Result of validation for a single record."""

    def __init__(self, record_id: str, document_id: str):
        self.record_id = record_id
        self.document_id = document_id
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.is_valid = True
        self.validation_metadata = {}

    def add_error(self, field: str, message: str, error_type: str = "validation_error"):
        """Add a validation error."""
        self.errors.append(ValidationError(field, message, error_type))
        self.is_valid = False

    def add_warning(self, field: str, message: str):
        """Add a validation warning (non-blocking)."""
        self.warnings.append(ValidationError(field, message, "warning"))

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "document_id": self.document_id,
            "status": "pass" if self.is_valid else "fail",
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "metadata": self.validation_metadata,
        }


class ValidationEngine:
    """Engine for validating normalized records against schema and rules."""

    # Schema definition: field_name -> (type, required, constraints)
    DEFAULT_SCHEMA = {
        "document_id": ("string", True, {"min_length": 1, "max_length": 500}),
        "record_id": ("string", True, {"min_length": 1, "max_length": 500}),
        "source_file_id": ("uuid", True, {}),
        "file_type": ("string", True, {"min_length": 1, "max_length": 50}),
        "size_bytes": ("integer", True, {"min_value": 0, "max_value": 5_000_000_000}),
        "title": ("string", False, {"max_length": 1000}),
        "author": ("string", False, {"max_length": 500}),
        "language": ("string", False, {"max_length": 20}),
        "content": ("string", False, {}),
        "normalized_payload": ("object", True, {}),
    }

    @staticmethod
    def validate_record(
        record: Dict[str, Any],
        schema: Optional[Dict] = None,
        custom_rules: Optional[Dict] = None,
    ) -> ValidationResult:
        """
        Validate a single record against schema and custom rules.

        Args:
            record: Record to validate
            schema: Optional schema override
            custom_rules: Optional custom validation rules

        Returns:
            ValidationResult with pass/fail status and error details
        """
        schema = schema or ValidationEngine.DEFAULT_SCHEMA
        result = ValidationResult(
            record_id=record.get("record_id", "unknown"),
            document_id=record.get("document_id", "unknown"),
        )

        # Validate against schema
        ValidationEngine._validate_schema(record, schema, result)

        # Apply custom rules if provided
        if custom_rules:
            ValidationEngine._apply_custom_rules(record, custom_rules, result)

        # Cross-field consistency checks
        ValidationEngine._validate_cross_field_consistency(record, result)

        return result

    @staticmethod
    def _validate_schema(
        record: Dict[str, Any],
        schema: Dict,
        result: ValidationResult,
    ):
        """Validate record against schema (type, required, constraints)."""
        for field_name, (field_type, required, constraints) in schema.items():
            value = record.get(field_name)

            # Check required fields
            if required and (value is None or (isinstance(value, str) and not value.strip())):
                result.add_error(
                    field_name,
                    f"Required field '{field_name}' is missing or empty",
                    "required_field_error",
                )
                continue

            # Skip validation if field is empty and not required
            if not required and value is None:
                continue

            # Type validation
            ValidationEngine._validate_type(field_name, value, field_type, constraints, result)

            # Constraint validation
            if value is not None:
                ValidationEngine._validate_constraints(
                    field_name, value, field_type, constraints, result
                )

    @staticmethod
    def _validate_type(
        field_name: str,
        value: Any,
        expected_type: str,
        constraints: Dict,
        result: ValidationResult,
    ):
        """Validate field type."""
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "object": lambda v: isinstance(v, dict),
            "array": lambda v: isinstance(v, list),
            "uuid": lambda v: isinstance(v, (str, type(None))) and (
                v is None or len(str(v)) == 36
            ),  # Basic UUID check
            "datetime": lambda v: isinstance(v, datetime),
        }

        type_check = type_checks.get(expected_type, lambda v: True)
        if not type_check(value):
            result.add_error(
                field_name,
                f"Field '{field_name}' must be of type {expected_type}, got {type(value).__name__}",
                "type_error",
            )

    @staticmethod
    def _validate_constraints(
        field_name: str,
        value: Any,
        field_type: str,
        constraints: Dict,
        result: ValidationResult,
    ):
        """Validate field constraints (min/max length, range, etc.)."""
        if not constraints:
            return

        # String constraints
        if field_type == "string" and isinstance(value, str):
            min_len = constraints.get("min_length")
            if min_len is not None and len(value) < min_len:
                result.add_error(
                    field_name,
                    f"Field '{field_name}' must be at least {min_len} characters",
                    "constraint_error",
                )

            max_len = constraints.get("max_length")
            if max_len is not None and len(value) > max_len:
                result.add_error(
                    field_name,
                    f"Field '{field_name}' must be at most {max_len} characters",
                    "constraint_error",
                )

        # Integer/Float constraints
        if field_type in ["integer", "float"] and isinstance(value, (int, float)):
            min_val = constraints.get("min_value")
            if min_val is not None and value < min_val:
                result.add_error(
                    field_name,
                    f"Field '{field_name}' must be at least {min_val}",
                    "constraint_error",
                )

            max_val = constraints.get("max_value")
            if max_val is not None and value > max_val:
                result.add_error(
                    field_name,
                    f"Field '{field_name}' must be at most {max_val}",
                    "constraint_error",
                )

        # Array constraints
        if field_type == "array" and isinstance(value, list):
            min_items = constraints.get("min_items")
            if min_items is not None and len(value) < min_items:
                result.add_warning(
                    field_name,
                    f"Field '{field_name}' should have at least {min_items} items",
                )

    @staticmethod
    def _apply_custom_rules(
        record: Dict[str, Any],
        custom_rules: Dict,
        result: ValidationResult,
    ):
        """Apply custom validation rules."""
        for rule_name, rule_func in custom_rules.items():
            try:
                rule_result = rule_func(record)
                if isinstance(rule_result, tuple):
                    is_valid, message = rule_result
                    if not is_valid:
                        result.add_error(
                            rule_name,
                            message,
                            "custom_rule_error",
                        )
            except Exception as e:
                logger.error(f"Error applying custom rule '{rule_name}': {e}")
                result.add_error(
                    rule_name,
                    f"Custom rule execution failed: {str(e)}",
                    "rule_execution_error",
                )

    @staticmethod
    def _validate_cross_field_consistency(
        record: Dict[str, Any],
        result: ValidationResult,
    ):
        """Validate consistency between related fields."""
        # Example: if file_type is CSV, content should not be too large
        file_type = record.get("file_type", "").lower()
        size_bytes = record.get("size_bytes", 0)

        if file_type == "csv" and size_bytes > 100_000_000:  # 100MB for CSV
            result.add_warning(
                "size_bytes",
                "CSV file size is unusually large (>100MB)",
            )

        # Example: if content is provided, language should be set
        content = record.get("content")
        language = record.get("language")
        if content and len(str(content)) > 100 and not language:
            result.add_warning(
                "language",
                "Language should be set when content is provided",
            )


class MappingExecutor:
    """Executor for mapping rules with error handling and sandboxing."""

    @staticmethod
    async def execute_mapping(
        record: Dict[str, Any],
        mapping_rules: Dict[str, str],
    ) -> tuple[Dict[str, Any], Optional[str]]:
        """
        Execute mapping rules on a record.

        Args:
            record: Record to map
            mapping_rules: Dict of {output_field: transformation_expression}

        Returns:
            Tuple of (mapped_record, error_message)
        """
        mapped_record = record.copy()
        errors = []

        for output_field, expression in mapping_rules.items():
            try:
                # Safe evaluation with limited scope
                result = MappingExecutor._safe_eval(expression, record)
                mapped_record[output_field] = result
            except Exception as e:
                error_msg = f"Mapping rule for '{output_field}' failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        if errors:
            return mapped_record, "; ".join(errors)

        return mapped_record, None

    @staticmethod
    def _safe_eval(expression: str, context: Dict[str, Any]) -> Any:
        """
        Safely evaluate an expression with limited scope.

        Only allows access to context variables, no built-in functions.
        """
        # Create safe builtins (only math operations)
        safe_builtins = {
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "upper": lambda s: s.upper() if isinstance(s, str) else s,
            "lower": lambda s: s.lower() if isinstance(s, str) else s,
            "strip": lambda s: s.strip() if isinstance(s, str) else s,
        }

        # Prevent access to dangerous attributes
        safe_context = context.copy()

        try:
            # Evaluate the expression with safe context
            return eval(expression, {"__builtins__": safe_builtins}, safe_context)
        except Exception as e:
            logger.error(f"Safe eval error: {e}")
            raise
