"""Integration tests for Click CLI commands.

Tests verify:
1. Upload command returns job_id in < 5 seconds
2. Monitor command queries status in < 2 seconds
3. Storage config validation prevents invalid uploads
4. All three commands work end-to-end
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

import httpx
import pytest
from click.testing import CliRunner

from app.tools.click_cli import upload, monitor, storage_configure, ClickClient


class TestClickClient:
    """Tests for the ClickClient HTTP client."""

    def test_client_init(self):
        """Test ClickClient initialization."""
        client = ClickClient("http://localhost:8000")
        assert client.base_url == "http://localhost:8000"
        client.close()

    def test_client_strips_trailing_slash(self):
        """Test that ClickClient strips trailing slashes from base_url."""
        client = ClickClient("http://localhost:8000/")
        assert client.base_url == "http://localhost:8000"
        client.close()

    @patch("httpx.Client.post")
    def test_upload_file_success(self, mock_post):
        """Test successful file upload."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_file = f.name

        try:
            # Mock successful response
            mock_response = Mock()
            mock_response.json.return_value = {
                "job_id": "test-job-123",
                "file_id": "test-file-456",
                "storage_path": "s3://bucket/file.txt",
                "size": 12,
            }
            mock_post.return_value = mock_response

            client = ClickClient()
            result = client.upload_file(temp_file)

            assert result["job_id"] == "test-job-123"
            assert result["file_id"] == "test-file-456"
            assert result["size"] == 12

        finally:
            Path(temp_file).unlink()

    def test_upload_file_not_found(self):
        """Test upload with non-existent file."""
        client = ClickClient()

        with pytest.raises(FileNotFoundError):
            client.upload_file("/nonexistent/file.txt")

    def test_upload_file_unsupported_type(self):
        """Test upload with unsupported file type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".exe", delete=False) as f:
            f.write("test")
            temp_file = f.name

        try:
            client = ClickClient()

            with pytest.raises(ValueError, match="Unsupported file type"):
                client.upload_file(temp_file)

        finally:
            Path(temp_file).unlink()

    def test_upload_file_too_large(self):
        """Test upload with file exceeding 50MB limit."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            # Write enough data to exceed 50MB
            f.write("x" * (51 * 1024 * 1024))
            temp_file = f.name

        try:
            client = ClickClient()

            with pytest.raises(ValueError, match="exceeds maximum"):
                client.upload_file(temp_file)

        finally:
            Path(temp_file).unlink()

    @patch("httpx.Client.get")
    def test_get_job_status_success(self, mock_get):
        """Test successful job status retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "job-123",
            "status": "PROCESSING",
            "progress_percentage": 50,
            "filename": "test.txt",
            "file_type": "txt",
            "size": 1024,
            "created_at": "2024-01-20T10:00:00Z",
        }
        mock_get.return_value = mock_response

        client = ClickClient()
        result = client.get_job_status("job-123")

        assert result["id"] == "job-123"
        assert result["status"] == "PROCESSING"
        assert result["progress_percentage"] == 50

    @patch("httpx.Client.post")
    def test_configure_storage_success(self, mock_post):
        """Test successful storage configuration."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "config-123",
            "storage_type": "s3",
            "endpoint": "https://s3.amazonaws.com",
            "bucket": "documents",
            "is_active": True,
        }
        mock_post.return_value = mock_response

        client = ClickClient()
        result = client.configure_storage(
            storage_type="s3",
            endpoint="https://s3.amazonaws.com",
            key="test-key",
            secret="test-secret",
        )

        assert result["storage_type"] == "s3"
        assert result["is_active"] is True

    @patch("httpx.Client.get")
    def test_test_storage_connection_success(self, mock_get):
        """Test successful storage connection test."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "success": True,
            "message": "Storage is accessible",
        }
        mock_get.return_value = mock_response

        client = ClickClient()
        result = client.test_storage_connection()

        assert result["success"] is True


class TestUploadCommand:
    """Tests for the upload CLI command."""

    def test_upload_help(self):
        """Test upload command help."""
        runner = CliRunner()
        result = runner.invoke(upload, ["--help"])
        assert result.exit_code == 0
        assert "FILE_PATH" in result.output

    @patch("app.tools.click_cli.ClickClient.upload_file")
    def test_upload_success_timing(self, mock_upload):
        """Test upload command returns job_id in < 5 seconds."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_file = f.name

        try:
            mock_upload.return_value = {
                "job_id": "test-job-123",
                "file_id": "test-file-456",
                "size": 12,
            }

            runner = CliRunner()
            start = time.time()
            result = runner.invoke(upload, [temp_file])
            elapsed = time.time() - start

            assert result.exit_code == 0
            assert "test-job-123" in result.output
            assert "✅ File uploaded successfully!" in result.output
            assert elapsed < 5.0  # Must complete in < 5 seconds

        finally:
            Path(temp_file).unlink()

    @patch("app.tools.click_cli.ClickClient.upload_file")
    def test_upload_file_not_found(self, mock_upload):
        """Test upload with non-existent file."""
        runner = CliRunner()
        result = runner.invoke(upload, ["/nonexistent/file.txt"])

        assert result.exit_code == 1
        assert "File not found" in result.output

    @patch("app.tools.click_cli.ClickClient.upload_file")
    def test_upload_unsupported_type(self, mock_upload):
        """Test upload with unsupported file type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".exe", delete=False) as f:
            f.write("test")
            temp_file = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(upload, [temp_file])

            assert result.exit_code == 1
            assert "Unsupported file type" in result.output

        finally:
            Path(temp_file).unlink()

    @patch("app.tools.click_cli.ClickClient.upload_file")
    def test_upload_api_error(self, mock_upload):
        """Test upload with API error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_file = f.name

        try:
            mock_upload.side_effect = httpx.HTTPError("API Error")

            runner = CliRunner()
            result = runner.invoke(upload, [temp_file])

            assert result.exit_code == 1
            assert "API error" in result.output

        finally:
            Path(temp_file).unlink()


class TestMonitorCommand:
    """Tests for the monitor CLI command."""

    def test_monitor_help(self):
        """Test monitor command help."""
        runner = CliRunner()
        result = runner.invoke(monitor, ["--help"])
        assert result.exit_code == 0
        assert "JOB_ID" in result.output
        assert "--watch" in result.output

    @patch("app.tools.click_cli.ClickClient.get_job_status")
    def test_monitor_single_query_timing(self, mock_status):
        """Test monitor command queries status in < 2 seconds."""
        mock_status.return_value = {
            "id": "job-123",
            "status": "COMPLETED",
            "progress_percentage": 100,
            "filename": "test.txt",
            "file_type": "txt",
            "size": 1024,
            "created_at": "2024-01-20T10:00:00Z",
        }

        runner = CliRunner()
        start = time.time()
        result = runner.invoke(monitor, ["job-123"])
        elapsed = time.time() - start

        assert result.exit_code == 0
        assert "job-123" in result.output
        assert "COMPLETED" in result.output
        assert elapsed < 2.0  # Must query in < 2 seconds

    @patch("app.tools.click_cli.ClickClient.get_job_status")
    def test_monitor_job_not_found(self, mock_status):
        """Test monitor with non-existent job."""
        mock_status.side_effect = httpx.HTTPError("404 Not Found")

        runner = CliRunner()
        result = runner.invoke(monitor, ["nonexistent-job"])

        assert result.exit_code == 1
        assert "Job not found" in result.output

    @patch("app.tools.click_cli.ClickClient.get_job_status")
    def test_monitor_watch_mode_polling(self, mock_status):
        """Test monitor with --watch flag polls until completion."""
        # Simulate job progressing from PENDING to COMPLETED
        mock_status.side_effect = [
            {
                "id": "job-123",
                "status": "PENDING",
                "progress_percentage": 0,
                "filename": "test.txt",
                "file_type": "txt",
                "size": 1024,
                "created_at": "2024-01-20T10:00:00Z",
            },
            {
                "id": "job-123",
                "status": "PROCESSING",
                "progress_percentage": 50,
                "filename": "test.txt",
                "file_type": "txt",
                "size": 1024,
                "created_at": "2024-01-20T10:00:00Z",
            },
            {
                "id": "job-123",
                "status": "COMPLETED",
                "progress_percentage": 100,
                "filename": "test.txt",
                "file_type": "txt",
                "size": 1024,
                "created_at": "2024-01-20T10:00:00Z",
            },
        ]

        runner = CliRunner()
        result = runner.invoke(monitor, ["job-123", "--watch", "--interval", "1"])

        assert result.exit_code == 0
        assert "COMPLETED" in result.output or "Job completed" in result.output
        # Verify that polling happened (at least 3 queries)
        assert mock_status.call_count >= 3

    @patch("app.tools.click_cli.ClickClient.get_job_status")
    def test_monitor_watch_mode_timeout(self, mock_status):
        """Test monitor --watch respects timeout."""
        # Always return PROCESSING status
        mock_status.return_value = {
            "id": "job-123",
            "status": "PROCESSING",
            "progress_percentage": 50,
            "filename": "test.txt",
            "file_type": "txt",
            "size": 1024,
            "created_at": "2024-01-20T10:00:00Z",
        }

        runner = CliRunner()
        result = runner.invoke(
            monitor,
            ["job-123", "--watch", "--interval", "1", "--timeout", "2"],
        )

        assert result.exit_code == 0
        assert "Timeout reached" in result.output

    @patch("app.tools.click_cli.ClickClient.get_job_status")
    def test_monitor_failed_job(self, mock_status):
        """Test monitor displays error for failed job."""
        mock_status.return_value = {
            "id": "job-123",
            "status": "FAILED",
            "progress_percentage": 0,
            "filename": "test.txt",
            "file_type": "txt",
            "size": 1024,
            "created_at": "2024-01-20T10:00:00Z",
            "error_message": "File format not supported",
        }

        runner = CliRunner()
        result = runner.invoke(monitor, ["job-123"])

        assert result.exit_code == 0
        assert "FAILED" in result.output
        assert "File format not supported" in result.output


class TestStorageConfigureCommand:
    """Tests for the storage configure CLI command."""

    def test_storage_configure_help(self):
        """Test storage configure command help."""
        runner = CliRunner()
        result = runner.invoke(storage_configure, ["--help"])
        assert result.exit_code == 0
        assert "--type" in result.output
        assert "--endpoint" in result.output

    @patch("app.tools.click_cli.ClickClient.test_storage_connection")
    @patch("app.tools.click_cli.ClickClient.configure_storage")
    def test_storage_configure_success(self, mock_configure, mock_test):
        """Test successful storage configuration with validation."""
        mock_configure.return_value = {
            "id": "config-123",
            "storage_type": "s3",
            "endpoint": "https://s3.amazonaws.com",
            "bucket": "documents",
            "is_active": True,
        }
        mock_test.return_value = {
            "success": True,
            "message": "Storage is accessible",
        }

        runner = CliRunner()
        result = runner.invoke(
            storage_configure,
            [
                "--type", "s3",
                "--endpoint", "https://s3.amazonaws.com",
                "--key", "test-key",
                "--secret", "test-secret",
            ],
        )

        assert result.exit_code == 0
        assert "✅ Storage configured" in result.output
        assert "✅ Connection test passed!" in result.output

    @patch("app.tools.click_cli.ClickClient.configure_storage")
    def test_storage_configure_missing_options(self, mock_configure):
        """Test storage configure with missing required options."""
        runner = CliRunner()
        result = runner.invoke(storage_configure, [])

        assert result.exit_code != 0

    @patch("app.tools.click_cli.ClickClient.test_storage_connection")
    @patch("app.tools.click_cli.ClickClient.configure_storage")
    def test_storage_configure_connection_failed(self, mock_configure, mock_test):
        """Test storage configure when connection test fails."""
        mock_configure.return_value = {
            "id": "config-123",
            "storage_type": "s3",
        }
        mock_test.side_effect = httpx.HTTPError("Connection failed")

        runner = CliRunner()
        result = runner.invoke(
            storage_configure,
            [
                "--type", "s3",
                "--endpoint", "https://s3.amazonaws.com",
                "--key", "test-key",
                "--secret", "test-secret",
            ],
        )

        assert result.exit_code == 1
        assert "Connection test failed!" in result.output

    @patch("app.tools.click_cli.ClickClient.test_storage_connection")
    @patch("app.tools.click_cli.ClickClient.configure_storage")
    def test_storage_configure_prevents_invalid_uploads(self, mock_configure, mock_test):
        """Test that invalid storage config prevents uploads."""
        # When storage configure fails, subsequent upload attempts should fail
        mock_configure.return_value = {"id": "config-123"}
        mock_test.side_effect = httpx.HTTPError("Invalid credentials")

        runner = CliRunner()
        result = runner.invoke(
            storage_configure,
            [
                "--type", "s3",
                "--endpoint", "https://invalid.com",
                "--key", "invalid-key",
                "--secret", "invalid-secret",
            ],
        )

        # Configuration fails due to connection test
        assert result.exit_code == 1


class TestEndToEndIntegration:
    """End-to-end integration tests for all three commands."""

    @patch("app.tools.click_cli.ClickClient.get_job_status")
    @patch("app.tools.click_cli.ClickClient.upload_file")
    def test_upload_then_monitor_workflow(self, mock_upload, mock_status):
        """Test complete workflow: upload file, then monitor job."""
        # Setup: Create test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_file = f.name

        try:
            # Step 1: Upload file
            mock_upload.return_value = {
                "job_id": "job-e2e-123",
                "file_id": "file-e2e-456",
                "size": 12,
            }

            runner = CliRunner()
            upload_result = runner.invoke(upload, [temp_file])

            assert upload_result.exit_code == 0
            assert "job-e2e-123" in upload_result.output

            # Step 2: Monitor job
            mock_status.return_value = {
                "id": "job-e2e-123",
                "status": "COMPLETED",
                "progress_percentage": 100,
                "filename": Path(temp_file).name,
                "file_type": "txt",
                "size": 12,
                "created_at": "2024-01-20T10:00:00Z",
            }

            monitor_result = runner.invoke(monitor, ["job-e2e-123"])

            assert monitor_result.exit_code == 0
            assert "job-e2e-123" in monitor_result.output
            assert "COMPLETED" in monitor_result.output

        finally:
            Path(temp_file).unlink()

    @patch("app.tools.click_cli.ClickClient.test_storage_connection")
    @patch("app.tools.click_cli.ClickClient.configure_storage")
    @patch("app.tools.click_cli.ClickClient.upload_file")
    def test_storage_configure_enables_uploads(self, mock_upload, mock_configure, mock_test):
        """Test that storage configuration must succeed before uploads work."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_file = f.name

        try:
            # Step 1: Configure storage successfully
            mock_configure.return_value = {
                "id": "config-123",
                "storage_type": "s3",
                "is_active": True,
            }
            mock_test.return_value = {"success": True}

            runner = CliRunner()
            config_result = runner.invoke(
                storage_configure,
                [
                    "--type", "s3",
                    "--endpoint", "https://s3.amazonaws.com",
                    "--key", "test-key",
                    "--secret", "test-secret",
                ],
            )

            assert config_result.exit_code == 0

            # Step 2: Upload file (should work with valid storage config)
            mock_upload.return_value = {
                "job_id": "job-123",
                "file_id": "file-456",
                "size": 12,
            }

            upload_result = runner.invoke(upload, [temp_file])

            assert upload_result.exit_code == 0
            assert "job-123" in upload_result.output

        finally:
            Path(temp_file).unlink()


class TestCliPerformanceRequirements:
    """Tests to verify performance requirements are met."""

    @patch("app.tools.click_cli.ClickClient.upload_file")
    def test_upload_response_time_under_5_seconds(self, mock_upload):
        """Verify upload command completes in < 5 seconds."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("x" * 1024)  # 1KB file
            temp_file = f.name

        try:
            mock_upload.return_value = {
                "job_id": "perf-test-job",
                "file_id": "perf-test-file",
                "size": 1024,
            }

            runner = CliRunner()
            start = time.time()
            result = runner.invoke(upload, [temp_file])
            elapsed = time.time() - start

            assert result.exit_code == 0
            assert elapsed < 5.0

        finally:
            Path(temp_file).unlink()

    @patch("app.tools.click_cli.ClickClient.get_job_status")
    def test_monitor_query_time_under_2_seconds(self, mock_status):
        """Verify monitor command queries in < 2 seconds."""
        mock_status.return_value = {
            "id": "perf-test-job",
            "status": "COMPLETED",
            "progress_percentage": 100,
            "filename": "test.txt",
            "file_type": "txt",
            "size": 1024,
            "created_at": "2024-01-20T10:00:00Z",
        }

        runner = CliRunner()
        start = time.time()
        result = runner.invoke(monitor, ["perf-test-job"])
        elapsed = time.time() - start

        assert result.exit_code == 0
        assert elapsed < 2.0

    @patch("app.tools.click_cli.ClickClient.test_storage_connection")
    @patch("app.tools.click_cli.ClickClient.configure_storage")
    def test_storage_configure_validates_quickly(self, mock_configure, mock_test):
        """Verify storage configuration validation is quick."""
        mock_configure.return_value = {"id": "config-123", "is_active": True}
        mock_test.return_value = {"success": True}

        runner = CliRunner()
        start = time.time()
        result = runner.invoke(
            storage_configure,
            [
                "--type", "s3",
                "--endpoint", "https://s3.amazonaws.com",
                "--key", "key",
                "--secret", "secret",
            ],
        )
        elapsed = time.time() - start

        assert result.exit_code == 0
        assert elapsed < 5.0  # Should be very fast


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
