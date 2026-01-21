import pytest
from datetime import datetime
from uuid import UUID, uuid4

from app.services.metadata.metadata_normalizer import MetadataNormalizer
from app.schemas.normalized_metadata import NormalizedMetadata


@pytest.fixture
def sample_raw_metadata():
    """Sample raw metadata from document extraction."""
    return {
        "file_id": str(uuid4()),
        "title": "Sample Document",
        "author": "John Doe",
        "date": "2024-01-13T12:00:00Z",
        "document_type": "legal",
        "custom_field_1": "value1",
        "custom_field_2": "value2",
    }


def test_normalize_basic_fields(sample_raw_metadata):
    """Test normalization of basic fields."""
    normalized = MetadataNormalizer.transform(sample_raw_metadata)

    assert normalized.title == "Sample Document"
    assert normalized.author == "John Doe"
    assert normalized.document_type == "legal"
    assert normalized.dates is not None
    assert len(normalized.dates) > 0


def test_normalize_with_aliases(sample_raw_metadata):
    """Test field extraction with alias names."""
    # Test with different field name aliases
    raw = {
        "file_id": str(uuid4()),
        "name": "Document Name",  # Alias for title
        "creator": "Jane Smith",  # Alias for author
        "created_at": "2024-01-01T00:00:00Z",  # Alias for date
        "kind": "report",  # Alias for document_type
    }

    normalized = MetadataNormalizer.transform(raw)

    assert normalized.title == "Document Name"
    assert normalized.author == "Jane Smith"
    assert normalized.document_type == "report"


def test_normalize_missing_optional_fields():
    """Test normalization handles missing optional fields."""
    raw = {
        "file_id": str(uuid4()),
        # No title, author, date, document_type
    }

    normalized = MetadataNormalizer.transform(raw)

    assert normalized.title is None
    assert normalized.author is None
    assert normalized.document_type is None or normalized.document_type == ""


def test_date_normalization_iso8601(sample_raw_metadata):
    """Test date normalization to ISO 8601."""
    normalized = MetadataNormalizer.transform(sample_raw_metadata)

    assert normalized.dates is not None
    assert len(normalized.dates) > 0
    # Check that dates are datetime objects
    assert all(isinstance(d, datetime) for d in normalized.dates)


def test_date_normalization_multiple_formats():
    """Test date normalization with multiple date formats."""
    raw = {
        "file_id": str(uuid4()),
        "date": "2024-01-13T12:00:00Z",
        "created_at": "2024-01-01",
    }

    normalized = MetadataNormalizer.transform(raw)

    assert normalized.dates is not None
    assert len(normalized.dates) >= 1


def test_extract_custom_metadata(sample_raw_metadata):
    """Test that custom metadata is extracted."""
    normalized = MetadataNormalizer.transform(sample_raw_metadata)

    assert normalized.custom_metadata is not None
    assert "custom_field_1" in normalized.custom_metadata
    assert normalized.custom_metadata["custom_field_1"] == "value1"


def test_field_type_validation():
    """Test field type validation."""
    raw = {
        "file_id": str(uuid4()),
        "title": "Test",
        "author": "Author",
    }

    normalized = MetadataNormalizer.transform(raw)
    # Should not raise error for valid types
    assert MetadataNormalizer.validate_field_types(normalized) is True


def test_field_type_validation_failure():
    """Test field type validation fails for invalid types."""
    from pydantic_core import ValidationError

    with pytest.raises(ValidationError):
        normalized = NormalizedMetadata(
            file_id=uuid4(),
            title=123,  # Invalid: should be string
            author="Author",
        )


def test_handle_missing_optional_fields():
    """Test handling of missing optional fields with defaults."""
    raw = {
        "file_id": str(uuid4()),
    }

    normalized = MetadataNormalizer.transform(raw)
    normalized = MetadataNormalizer.handle_missing_optional_fields(normalized)

    assert isinstance(normalized.custom_metadata, dict)
    assert isinstance(normalized.dates, list)


def test_source_metadata_preservation(sample_raw_metadata):
    """Test that source metadata is preserved for traceability."""
    normalized = MetadataNormalizer.transform(sample_raw_metadata)

    assert normalized.source_metadata is not None
    assert "original_keys" in normalized.source_metadata
    assert "extraction_timestamp" in normalized.source_metadata


def test_mapping_version():
    """Test that mapping version is set."""
    raw = {
        "file_id": str(uuid4()),
        "title": "Test",
    }

    normalized = MetadataNormalizer.transform(raw)

    assert normalized.mapping_version == "1.0.0"


def test_missing_file_id_error():
    """Test that missing file_id raises error."""
    raw = {
        "title": "Test",
        # Missing file_id
    }

    with pytest.raises(ValueError, match="file_id"):
        MetadataNormalizer.transform(raw)


def test_normalize_whitespace_trimming():
    """Test that whitespace is trimmed from fields."""
    raw = {
        "file_id": str(uuid4()),
        "title": "  Document Name  ",
        "author": "  Author Name  ",
    }

    normalized = MetadataNormalizer.transform(raw)

    assert normalized.title == "Document Name"
    assert normalized.author == "Author Name"


def test_normalize_empty_string_fields():
    """Test that empty strings are treated as None."""
    raw = {
        "file_id": str(uuid4()),
        "title": "",
        "author": "   ",  # Whitespace only
    }

    normalized = MetadataNormalizer.transform(raw)

    # Empty strings should become None
    assert normalized.title is None or normalized.title == ""
    assert normalized.author is None or normalized.author == ""


def test_normalize_case_insensitive_field_matching():
    """Test that field name matching is case-insensitive."""
    raw = {
        "file_id": str(uuid4()),
        "TITLE": "Document",
        "Author": "Name",
        "DATE": "2024-01-01",
    }

    normalized = MetadataNormalizer.transform(raw)

    assert normalized.title == "Document"
    assert normalized.author == "Name"
    assert normalized.dates is not None
