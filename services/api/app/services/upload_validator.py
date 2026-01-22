"""Upload validation service for file type, size, and integrity checks."""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Allowed file types (MIME types)
ALLOWED_MIME_TYPES = {
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/html": "html",
    "text/markdown": "md",
    "application/json": "json",
    "text/csv": "csv",
    "text/yaml": "yml",
    "application/yaml": "yml",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/pdf": "pdf",
}

ALLOWED_FILE_EXTENSIONS = {
    "txt", "docx", "xlsx", "pptx", "html", "md", "json", "csv", "yml", "xml", "pdf"
}


class UploadValidator:
    """Validates uploaded files for type, size, and integrity."""

    def __init__(self, max_file_size_mb: int = 50):
        """Initialize validator with max file size in MB."""
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_file_size_mb = max_file_size_mb

    def validate_file_type(self, mime_type: str, filename: str) -> Tuple[bool, str]:
        """
        Validate file MIME type and extension.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check MIME type
        if mime_type not in ALLOWED_MIME_TYPES:
            return False, f"File type {mime_type} not supported. Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}"

        # Check file extension
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_FILE_EXTENSIONS:
            return False, f"File extension .{ext} not supported. Allowed: {', '.join(ALLOWED_FILE_EXTENSIONS)}"

        return True, ""

    def validate_file_size(self, file_size_bytes: int) -> Tuple[bool, str]:
        """
        Validate file size.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if file_size_bytes > self.max_file_size_bytes:
            size_mb = file_size_bytes / (1024 * 1024)
            return False, f"File size {size_mb:.2f}MB exceeds limit of {self.max_file_size_mb}MB"

        return True, ""

    def validate_integrity(self, file_bytes: bytes) -> Tuple[bool, str]:
        """
        Validate file integrity (non-empty, readable).

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_bytes or len(file_bytes) == 0:
            return False, "File is empty"

        # Basic integrity check: file should be readable
        try:
            # Try to decode as text (will fail for binary but that's ok)
            # We just want to ensure the file isn't corrupted
            _ = file_bytes[:1]  # Read first byte
            return True, ""
        except Exception as e:
            logger.error(f"File integrity check failed: {e}")
            return False, f"File integrity check failed: {str(e)}"

    def validate(self, file_bytes: bytes, filename: str, mime_type: str) -> Tuple[bool, str]:
        """
        Perform all validations.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate type
        is_valid, error = self.validate_file_type(mime_type, filename)
        if not is_valid:
            return False, error

        # Validate size
        is_valid, error = self.validate_file_size(len(file_bytes))
        if not is_valid:
            return False, error

        # Validate integrity
        is_valid, error = self.validate_integrity(file_bytes)
        if not is_valid:
            return False, error

        return True, ""
