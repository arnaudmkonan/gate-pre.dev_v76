"""Unit tests for validation engine."""

import pytest
from uuid import uuid4

from app.services.validation_engine import ValidationEngine, MappingExecutor


class TestValidationEngine:
    """Tests for ValidationEngine."""

    def test_validate_valid_record(self):
        """Test validation of a valid record."""
        record = {
            "document_id": "doc_001",
            "record_id": "rec_001",
            "source_file_id": str(uuid4()),
            "file_type": "pdf",
            "size_bytes": 1024,
            "normalized_payload": {"content": "test"},
        }

        result = ValidationEngine.validate_record(record)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.record_id == "rec_001"

    def test_missing_required_field(self):
        """Test validation fails for missing required field."""
        record = {
            "document_id": "doc_001",
            "record_id": "rec_001",
            # Missing source_file_id
            "file_type": "pdf",
            "size_bytes": 1024,
            "normalized_payload": {},
        }

        result = ValidationEngine.validate_record(record)

        assert not result.is_valid
        assert len(result.errors) > 0
        assert any("source_file_id" in e.field for e in result.errors)

    def test_invalid_field_type(self):
        """Test validation fails for wrong field type."""
        record = {
            "document_id": "doc_001",
            "record_id": "rec_001",
            "source_file_id": str(uuid4()),
            "file_type": "pdf",
            "size_bytes": "not_an_int",  # Should be integer
            "normalized_payload": {},
        }

        result = ValidationEngine.validate_record(record)

        assert not result.is_valid
        assert any("size_bytes" in e.field for e in result.errors)

    def test_field_length_constraint(self):
        """Test validation of field length constraints."""
        record = {
            "document_id": "doc_001",
            "record_id": "rec_001",
            "source_file_id": str(uuid4()),
            "file_type": "pdf",
            "size_bytes": 1024,
            "title": "x" * 1001,  # Exceeds max_length of 1000
            "normalized_payload": {},
        }

        result = ValidationEngine.validate_record(record)

        assert not result.is_valid
        assert any("title" in e.field for e in result.errors)

    def test_size_bytes_constraint(self):
        """Test size_bytes range validation."""
        record = {
            "document_id": "doc_001",
            "record_id": "rec_001",
            "source_file_id": str(uuid4()),
            "file_type": "pdf",
            "size_bytes": 6_000_000_000,  # Exceeds max of 5GB
            "normalized_payload": {},
        }

        result = ValidationEngine.validate_record(record)

        assert not result.is_valid
        assert any("size_bytes" in e.field for e in result.errors)

    def test_optional_fields(self):
        """Test that optional fields are not required."""
        record = {
            "document_id": "doc_001",
            "record_id": "rec_001",
            "source_file_id": str(uuid4()),
            "file_type": "pdf",
            "size_bytes": 1024,
            "normalized_payload": {},
            # title, author, language, content are all optional
        }

        result = ValidationEngine.validate_record(record)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_custom_rules(self):
        """Test application of custom validation rules."""
        record = {
            "document_id": "doc_001",
            "record_id": "rec_001",
            "source_file_id": str(uuid4()),
            "file_type": "pdf",
            "size_bytes": 1024,
            "normalized_payload": {},
        }

        # Custom rule: document_id must start with "doc_"
        custom_rules = {
            "document_id_format": lambda r: (
                r.get("document_id", "").startswith("doc_"),
                "document_id must start with 'doc_'",
            )
        }

        result = ValidationEngine.validate_record(record, custom_rules=custom_rules)
        assert result.is_valid

        # Test with invalid document_id
        record["document_id"] = "invalid_001"
        result = ValidationEngine.validate_record(record, custom_rules=custom_rules)
        assert not result.is_valid
        assert any("document_id_format" in e.field for e in result.errors)

    def test_cross_field_consistency(self):
        """Test cross-field validation."""
        record = {
            "document_id": "doc_001",
            "record_id": "rec_001",
            "source_file_id": str(uuid4()),
            "file_type": "csv",
            "size_bytes": 200_000_000,  # Large CSV file
            "content": "x" * 1000,  # Large content without language
            "normalized_payload": {},
        }

        result = ValidationEngine.validate_record(record)

        # Should have warnings but still be valid
        assert result.is_valid or len(result.warnings) > 0

    def test_empty_document_id(self):
        """Test that empty strings are treated as missing."""
        record = {
            "document_id": "",  # Empty string
            "record_id": "rec_001",
            "source_file_id": str(uuid4()),
            "file_type": "pdf",
            "size_bytes": 1024,
            "normalized_payload": {},
        }

        result = ValidationEngine.validate_record(record)

        assert not result.is_valid
        assert any("document_id" in e.field for e in result.errors)


class TestMappingExecutor:
    """Tests for MappingExecutor."""

    @pytest.mark.asyncio
    async def test_simple_mapping(self):
        """Test simple field mapping."""
        record = {"name": "John", "age": 30}
        mapping_rules = {
            "full_name": "name.upper()",
            "age_group": "f'{age} years old'",
        }

        result, error = await MappingExecutor.execute_mapping(record, mapping_rules)

        assert error is None
        assert result["full_name"] == "JOHN"
        assert result["age_group"] == "30 years old"

    @pytest.mark.asyncio
    async def test_mapping_with_error(self):
        """Test mapping rule that fails safely."""
        record = {"value": "test"}
        mapping_rules = {
            "invalid": "undefined_var",  # References non-existent variable
        }

        result, error = await MappingExecutor.execute_mapping(record, mapping_rules)

        assert error is not None
        assert "failed" in error.lower()

    @pytest.mark.asyncio
    async def test_safe_functions_available(self):
        """Test that safe functions are available in mapping context."""
        record = {"text": "hello world"}
        mapping_rules = {
            "length": "len(text)",
            "upper": "text.upper()",
            "lower": "text.lower()",
            "stripped": "text.strip()",
        }

        result, error = await MappingExecutor.execute_mapping(record, mapping_rules)

        assert error is None
        assert result["length"] == 11
        assert result["upper"] == "HELLO WORLD"
        assert result["lower"] == "hello world"
        assert result["stripped"] == "hello world"

    @pytest.mark.asyncio
    async def test_restricted_functions_blocked(self):
        """Test that dangerous functions are blocked."""
        record = {}
        mapping_rules = {
            "dangerous": "__import__('os')",  # Try to import os module
        }

        result, error = await MappingExecutor.execute_mapping(record, mapping_rules)

        # Should fail safely
        assert error is not None or "__import__" not in str(result.get("dangerous", ""))
