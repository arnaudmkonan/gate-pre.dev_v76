"""Local filesystem storage service for development and testing."""
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default local storage path
LOCAL_STORAGE_PATH = os.environ.get("LOCAL_STORAGE_PATH", "/app/storage")


class LocalStorageService:
    """Service for local filesystem storage operations (dev/testing only)."""

    def __init__(self, base_path: str = LOCAL_STORAGE_PATH):
        """Initialize local storage service."""
        self.base_path = Path(base_path)
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """Ensure storage directories exist."""
        uploads_dir = self.base_path / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage initialized at: {self.base_path}")

    def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> dict:
        """Upload file to local storage and return metadata."""
        try:
            # Compute checksum
            checksum = hashlib.sha256(file_bytes).hexdigest()
            
            # Create unique filename to avoid collisions
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{timestamp}_{filename}"
            storage_path = f"uploads/{safe_filename}"
            
            # Full path on filesystem
            full_path = self.base_path / storage_path

            # Write file
            with open(full_path, "wb") as f:
                f.write(file_bytes)

            logger.info(f"File uploaded locally: {storage_path}, checksum: {checksum}")

            return {
                "storage_path": storage_path,
                "checksum": checksum,
                "file_size": len(file_bytes),
                "local_path": str(full_path),
            }
        except Exception as e:
            logger.error(f"Local storage upload error: {e}")
            raise

    def get_file(self, storage_path: str) -> bytes:
        """Get file content from local storage."""
        try:
            full_path = self.base_path / storage_path
            with open(full_path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {storage_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            raise

    def generate_signed_url(
        self,
        storage_path: str,
        ttl_seconds: int = 3600,
    ) -> tuple[str, datetime]:
        """Generate a fake signed URL for local files (just returns file URL)."""
        # For local storage, return a file:// URL or API endpoint
        # In production, this would be a real signed URL
        local_url = f"file://{self.base_path / storage_path}"
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        
        logger.info(f"Local URL generated for: {storage_path}")
        return local_url, expires_at

    def get_object_metadata(self, storage_path: str) -> dict:
        """Get object metadata from local storage."""
        try:
            full_path = self.base_path / storage_path
            stat = os.stat(full_path)

            return {
                "file_size": stat.st_size,
                "mime_type": "application/octet-stream",
                "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                "metadata": {},
            }
        except FileNotFoundError:
            logger.error(f"File not found: {storage_path}")
            raise
        except Exception as e:
            logger.error(f"Error getting object metadata: {e}")
            raise

    def delete_file(self, storage_path: str) -> bool:
        """Delete file from local storage."""
        try:
            full_path = self.base_path / storage_path
            os.remove(full_path)
            logger.info(f"File deleted: {storage_path}")
            return True
        except FileNotFoundError:
            logger.warning(f"File already deleted or not found: {storage_path}")
            return False
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            raise

    def test_connection(self) -> bool:
        """Test local storage connection (always succeeds if dir exists)."""
        try:
            self._ensure_storage_dir()
            # Write a test file
            test_path = self.base_path / ".test"
            test_path.write_text("test")
            test_path.unlink()
            logger.info("Local storage connection test successful")
            return True
        except Exception as e:
            logger.error(f"Local storage connection test failed: {e}")
            raise

    def list_files(self, prefix: str = "uploads/") -> list[dict]:
        """List files in storage."""
        try:
            prefix_path = self.base_path / prefix
            files = []
            
            if prefix_path.exists():
                for f in prefix_path.iterdir():
                    if f.is_file():
                        stat = f.stat()
                        files.append({
                            "path": str(f.relative_to(self.base_path)),
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                        })
            
            return files
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            raise
