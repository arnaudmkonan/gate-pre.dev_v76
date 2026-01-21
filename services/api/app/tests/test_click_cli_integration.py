"""Integration tests for Click CLI commands against live API.

Tests verify:
1. Upload command returns job_id in < 5 seconds (real HTTP requests)
2. Monitor command queries status in < 2 seconds (real HTTP requests)
3. Storage configure command validates connection without mocking
4. All commands work end-to-end with actual API responses
5. Response times meet performance requirements

These tests run against a live API instance without mocking HTTP calls.
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path
from datetime import datetime

import httpx
import pytest
from click.testing import CliRunner

from app.tools.click_cli import upload, monitor, storage_configure, ClickClient


class TestClickClientIntegration:
    """Integration tests for ClickClient with live API."""

    @pytest.fixture
    def api_url(self):
        """Get API URL from environment or use default."""
        return "http://localhost:8000"

    @pytest.fixture
    def test_file(self):
        """Create a temporary test file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Integration test content for upload")
            temp_file = f.name

        yield temp_file

        # Cleanup
        Path(temp_file).unlink(missing_ok=True)

    def test_client_init_real_api(self, api_url):
        """Test ClickClient can connect to real API."""
        client = ClickClient(api_url)
        assert client.base_url == api_url
        client.close()

    def test_upload_file_real_api(self, api_url, test_file):
        """Test uploading a real file to the API."""
        client = ClickClient(api_url)

        try:
            # Measure upload time
            start_time = time.time()
            result = client.upload_file(test_file)
            elapsed_time = time.time() - start_time

            # Verify result
            assert "job_id" in result
            assert "file_id" in result
            assert result["file_id"] is not None
            assert result["job_id"] is not None
            assert elapsed_time < 5.0, f"Upload took {elapsed_time}s, expected < 5s"

            print(f"\n✅ Upload completed in {elapsed_time:.3f}s")
            print(f"   Job ID: {result['job_id']}")

            return result["job_id"]

        finally:
            client.close()

    def test_get_job_status_real_api(self, api_url, test_file):
        """Test querying job status from the API."""
        client = ClickClient(api_url)

        try:
            # First upload a file
            upload_result = client.upload_file(test_file)
            job_id = upload_result["job_id"]

            # Now query the job status
            start_time = time.time()
            job_status = client.get_job_status(job_id)
            query_time = time.time() - start_time

            # Verify response
            assert job_status["id"] == job_id
            assert "status" in job_status
            assert "filename" in job_status
            assert query_time < 2.0, f"Query took {query_time}s, expected < 2s"

            print(f"\n✅ Job status query completed in {query_time:.3f}s")
            print(f"   Status: {job_status['status']}")
            print(f"   Progress: {job_status.get('progress_percentage', 0)}%")

        finally:
            client.close()

    def test_configure_storage_real_api(self, api_url):
        """Test storage configuration against real API."""
        client = ClickClient(api_url)

        try:
            # Configure storage
            start_time = time.time()
            result = client.configure_storage(
                storage_type="s3",
                endpoint="http://localhost:9000",
                key="test-key",
                secret="test-secret",
                bucket="test-bucket",
                region="us-east-1",
            )
            config_time = time.time() - start_time

            # Verify response
            assert "id" in result or "status" in result
            assert config_time < 5.0

            print(f"\n✅ Storage configured in {config_time:.3f}s")

        finally:
            client.close()

    def test_test_storage_connection_real_api(self, api_url):
        """Test storage connection validation."""
        client = ClickClient(api_url)

        try:
            # First configure storage
            client.configure_storage(
                storage_type="s3",
                endpoint="http://localhost:9000",
                key="test-key",
                secret="test-secret",
                bucket="test-bucket",
            )

            # Now test the connection
            start_time = time.time()
            test_result = client.test_storage_connection()
            test_time = time.time() - start_time

            # Verify result
            assert isinstance(test_result, dict)
            assert test_time < 2.0

            print(f"\n✅ Storage connection test completed in {test_time:.3f}s")
            print(f"   Result: {test_result.get('message', 'Unknown')}")

        finally:
            client.close()


class TestUploadCommandIntegration:
    """Integration tests for the upload CLI command with live API."""

    @pytest.fixture
    def test_file(self):
        """Create a temporary test file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("CLI integration test content")
            temp_file = f.name

        yield temp_file

        # Cleanup
        Path(temp_file).unlink(missing_ok=True)

    def test_upload_command_success(self, test_file):
        """Test upload command with real API."""
        runner = CliRunner()

        start_time = time.time()
        result = runner.invoke(
            upload,
            [test_file, "--api-url", "http://localhost:8000"]
        )
        elapsed_time = time.time() - start_time

        # Verify execution
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "✅ File uploaded successfully!" in result.output
        assert "Job ID:" in result.output
        assert elapsed_time < 5.0, f"Upload took {elapsed_time}s, expected < 5s"

        print(f"\n✅ Upload command completed in {elapsed_time:.3f}s")
        print(f"Output:\n{result.output}")

        # Extract job_id from output
        lines = result.output.split("\n")
        job_id_line = [l for l in lines if "Job ID:" in l]
        if job_id_line:
            job_id = job_id_line[0].split("Job ID:")[-1].strip()
            return job_id

    def test_upload_large_file(self):
        """Test uploading a larger file (close to limit)."""
        # Create a 5MB test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("x" * (5 * 1024 * 1024))  # 5MB
            temp_file = f.name

        try:
            runner = CliRunner()

            start_time = time.time()
            result = runner.invoke(
                upload,
                [temp_file, "--api-url", "http://localhost:8000"]
            )
            elapsed_time = time.time() - start_time

            assert result.exit_code == 0, f"Command failed: {result.output}"
            assert "File uploaded successfully" in result.output
            assert elapsed_time < 5.0

            print(f"\n✅ Large file upload completed in {elapsed_time:.3f}s")

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_upload_unsupported_file_type(self):
        """Test upload rejects unsupported file types."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".exe", delete=False) as f:
            f.write("fake executable")
            temp_file = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                upload,
                [temp_file, "--api-url", "http://localhost:8000"]
            )

            assert result.exit_code == 1
            assert "Unsupported file type" in result.output

        finally:
            Path(temp_file).unlink(missing_ok=True)


class TestMonitorCommandIntegration:
    """Integration tests for the monitor CLI command with live API."""

    @pytest.fixture
    def job_id(self):
        """Create a job by uploading a file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Monitor test content")
            temp_file = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                upload,
                [temp_file, "--api-url", "http://localhost:8000"]
            )

            # Extract job_id from output
            lines = result.output.split("\n")
            job_id_line = [l for l in lines if "Job ID:" in l]
            if job_id_line:
                job_id = job_id_line[0].split("Job ID:")[-1].strip()
                yield job_id
            else:
                pytest.skip("Could not create test job")

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_monitor_command_single_query(self, job_id):
        """Test monitor command queries status in < 2 seconds."""
        runner = CliRunner()

        start_time = time.time()
        result = runner.invoke(
            monitor,
            [job_id, "--api-url", "http://localhost:8000"]
        )
        elapsed_time = time.time() - start_time

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert job_id in result.output
        assert elapsed_time < 2.0, f"Query took {elapsed_time}s, expected < 2s"

        print(f"\n✅ Monitor query completed in {elapsed_time:.3f}s")
        print(f"Output:\n{result.output}")

    def test_monitor_command_with_watch(self, job_id):
        """Test monitor command with --watch mode."""
        runner = CliRunner()

        # Run with short timeout
        result = runner.invoke(
            monitor,
            [
                job_id,
                "--watch",
                "--interval", "1",
                "--timeout", "3",
                "--api-url", "http://localhost:8000"
            ]
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert job_id in result.output
        # Should reach timeout or completion
        assert "Timeout reached" in result.output or "completed" in result.output.lower()

        print(f"\n✅ Monitor watch mode completed")
        print(f"Output:\n{result.output}")

    def test_monitor_invalid_job_id(self):
        """Test monitor with non-existent job ID."""
        runner = CliRunner()
        result = runner.invoke(
            monitor,
            ["nonexistent-job-id", "--api-url", "http://localhost:8000"]
        )

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

        print(f"\n✅ Monitor correctly rejected invalid job ID")


class TestStorageConfigureCommandIntegration:
    """Integration tests for storage configure command with live API."""

    def test_storage_configure_success(self):
        """Test storage configuration with valid credentials."""
        runner = CliRunner()

        result = runner.invoke(
            storage_configure,
            [
                "--type", "s3",
                "--endpoint", "http://localhost:9000",
                "--key", "test-key",
                "--secret", "test-secret",
                "--bucket", "test-bucket",
                "--region", "us-east-1",
                "--api-url", "http://localhost:8000"
            ]
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "✅ Storage configured" in result.output
        assert "✅ Connection test passed!" in result.output

        print(f"\n✅ Storage configure completed")
        print(f"Output:\n{result.output}")

    def test_storage_configure_missing_options(self):
        """Test storage configure with missing required options."""
        runner = CliRunner()

        result = runner.invoke(
            storage_configure,
            ["--api-url", "http://localhost:8000"]
        )

        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output

        print(f"\n✅ Storage configure correctly rejected missing options")


class TestEndToEndIntegration:
    """End-to-end integration tests with live API."""

    def test_upload_monitor_workflow(self):
        """Test complete workflow: upload → monitor → check status."""
        # Step 1: Upload a file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("E2E test content")
            temp_file = f.name

        try:
            runner = CliRunner()

            # Upload
            upload_result = runner.invoke(
                upload,
                [temp_file, "--api-url", "http://localhost:8000"]
            )

            assert upload_result.exit_code == 0
            assert "✅ File uploaded successfully!" in upload_result.output

            # Extract job_id
            lines = upload_result.output.split("\n")
            job_id_line = [l for l in lines if "Job ID:" in l]
            if not job_id_line:
                pytest.skip("Could not extract job ID from upload response")

            job_id = job_id_line[0].split("Job ID:")[-1].strip()

            # Step 2: Monitor the job
            monitor_result = runner.invoke(
                monitor,
                [job_id, "--api-url", "http://localhost:8000"]
            )

            assert monitor_result.exit_code == 0
            assert job_id in monitor_result.output

            print(f"\n✅ E2E workflow completed")
            print(f"   Job ID: {job_id}")
            print(f"   Upload: OK")
            print(f"   Monitor: OK")

        finally:
            Path(temp_file).unlink(missing_ok=True)

    def test_storage_configure_then_upload(self):
        """Test that storage must be configured before upload works."""
        # Step 1: Configure storage
        runner = CliRunner()

        config_result = runner.invoke(
            storage_configure,
            [
                "--type", "s3",
                "--endpoint", "http://localhost:9000",
                "--key", "test-key",
                "--secret", "test-secret",
                "--bucket", "test-bucket",
                "--api-url", "http://localhost:8000"
            ]
        )

        assert config_result.exit_code == 0

        # Step 2: Upload a file (should work with valid storage)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Upload after configure test")
            temp_file = f.name

        try:
            upload_result = runner.invoke(
                upload,
                [temp_file, "--api-url", "http://localhost:8000"]
            )

            assert upload_result.exit_code == 0
            assert "✅ File uploaded successfully!" in upload_result.output

            print(f"\n✅ Storage configure → upload workflow completed")

        finally:
            Path(temp_file).unlink(missing_ok=True)


class TestPerformanceRequirements:
    """Tests to verify all performance requirements are met."""

    @pytest.fixture
    def test_file(self):
        """Create a temporary test file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Performance test content")
            temp_file = f.name

        yield temp_file

        Path(temp_file).unlink(missing_ok=True)

    def test_upload_under_5_seconds(self, test_file):
        """Verify upload completes in < 5 seconds."""
        runner = CliRunner()

        start_time = time.time()
        result = runner.invoke(
            upload,
            [test_file, "--api-url", "http://localhost:8000"]
        )
        elapsed_time = time.time() - start_time

        assert result.exit_code == 0
        assert elapsed_time < 5.0

        print(f"\n⏱️  Upload time: {elapsed_time:.3f}s (target: < 5s) ✅")

    def test_monitor_query_under_2_seconds(self, test_file):
        """Verify monitor query completes in < 2 seconds."""
        runner = CliRunner()

        # Upload a file first
        upload_result = runner.invoke(
            upload,
            [test_file, "--api-url", "http://localhost:8000"]
        )

        lines = upload_result.output.split("\n")
        job_id_line = [l for l in lines if "Job ID:" in l]
        if not job_id_line:
            pytest.skip("Could not extract job ID")

        job_id = job_id_line[0].split("Job ID:")[-1].strip()

        # Now monitor
        start_time = time.time()
        monitor_result = runner.invoke(
            monitor,
            [job_id, "--api-url", "http://localhost:8000"]
        )
        elapsed_time = time.time() - start_time

        assert monitor_result.exit_code == 0
        assert elapsed_time < 2.0

        print(f"\n⏱️  Monitor query time: {elapsed_time:.3f}s (target: < 2s) ✅")

    def test_storage_configure_quick(self):
        """Verify storage configure is quick."""
        runner = CliRunner()

        start_time = time.time()
        result = runner.invoke(
            storage_configure,
            [
                "--type", "s3",
                "--endpoint", "http://localhost:9000",
                "--key", "test-key",
                "--secret", "test-secret",
                "--bucket", "test-bucket",
                "--api-url", "http://localhost:8000"
            ]
        )
        elapsed_time = time.time() - start_time

        assert result.exit_code == 0
        assert elapsed_time < 5.0

        print(f"\n⏱️  Storage configure time: {elapsed_time:.3f}s (target: < 5s) ✅")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
