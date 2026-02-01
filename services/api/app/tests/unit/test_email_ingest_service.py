"""
Unit tests for Email Ingestion Service.

Tests IMAP connection, attachment extraction, and processing workflow.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from email.message import EmailMessage

from app.services.email_ingest_service import (
    EmailIngestService,
    EmailAttachment,
    EmailMessage as EmailMsg,
    IngestionResult,
    EmailProvider,
    check_email_configured,
    get_email_status,
)


class TestEmailIngestService:
    """Tests for EmailIngestService class."""
    
    def test_init_with_defaults(self):
        """Test service initialization with default settings."""
        service = EmailIngestService()
        
        # Should use settings from config if not provided
        assert service.inbox_folder == "INBOX"
        assert service.use_ssl is True
    
    def test_init_with_custom_settings(self):
        """Test service initialization with custom settings."""
        service = EmailIngestService(
            host="imap.test.com",
            port=143,
            username="test@test.com",
            password="password123",
            use_ssl=False,
            inbox_folder="Documents",
            processed_folder="Done"
        )
        
        assert service.host == "imap.test.com"
        assert service.port == 143
        assert service.username == "test@test.com"
        assert service.use_ssl is False
        assert service.inbox_folder == "Documents"
        assert service.processed_folder == "Done"
    
    def test_is_configured_false_when_missing_host(self):
        """Test is_configured returns False when host is missing."""
        service = EmailIngestService(
            host=None,
            username="test@test.com",
            password="pass"
        )
        assert service.is_configured is False
    
    def test_is_configured_false_when_missing_password(self):
        """Test is_configured returns False when password is missing."""
        service = EmailIngestService(
            host="imap.test.com",
            username="test@test.com",
            password=None
        )
        assert service.is_configured is False
    
    def test_is_configured_true_when_all_present(self):
        """Test is_configured returns True when all required settings present."""
        service = EmailIngestService(
            host="imap.test.com",
            username="test@test.com",
            password="password123"
        )
        assert service.is_configured is True


class TestEmailAttachment:
    """Tests for EmailAttachment dataclass."""
    
    def test_attachment_creation(self):
        """Test creating an attachment."""
        attachment = EmailAttachment(
            filename="invoice.pdf",
            content_type="application/pdf",
            data=b"PDF content here",
            size=100
        )
        
        assert attachment.filename == "invoice.pdf"
        assert attachment.content_type == "application/pdf"
        assert attachment.size == 100


class TestIngestionResult:
    """Tests for IngestionResult dataclass."""
    
    def test_success_result(self):
        """Test successful ingestion result."""
        result = IngestionResult(
            email_id="msg123",
            success=True,
            documents_created=3,
            document_ids=["doc1", "doc2", "doc3"]
        )
        
        assert result.success is True
        assert result.documents_created == 3
        assert len(result.document_ids) == 3
    
    def test_failed_result(self):
        """Test failed ingestion result."""
        result = IngestionResult(
            email_id="msg456",
            success=False,
            documents_created=0,
            error="Connection failed"
        )
        
        assert result.success is False
        assert result.error == "Connection failed"


class TestEmailParsing:
    """Tests for email parsing methods."""
    
    def test_decode_header_simple(self):
        """Test decoding simple header."""
        service = EmailIngestService(
            host="test", 
            username="test",
            password="test"
        )
        
        result = service._decode_header("Simple Subject")
        assert result == "Simple Subject"
    
    def test_parse_sender_with_name_and_email(self):
        """Test parsing sender with name and email."""
        service = EmailIngestService(
            host="test",
            username="test", 
            password="test"
        )
        
        name, email = service._parse_sender("John Doe <john@example.com>")
        assert name == "John Doe"
        assert email == "john@example.com"
    
    def test_parse_sender_email_only(self):
        """Test parsing sender with email only."""
        service = EmailIngestService(
            host="test",
            username="test",
            password="test"
        )
        
        name, email = service._parse_sender("john@example.com")
        # When no angle brackets, the whole email is returned
        assert email == "john@example.com"
        assert name == "john@example.com"


class TestAllowedExtensions:
    """Tests for file extension validation."""
    
    def test_allowed_extensions(self):
        """Test that allowed extensions are properly defined."""
        service = EmailIngestService(
            host="test",
            username="test",
            password="test"
        )
        
        # Check essential extensions are allowed
        assert 'pdf' in service.ALLOWED_EXTENSIONS
        assert 'xlsx' in service.ALLOWED_EXTENSIONS
        assert 'png' in service.ALLOWED_EXTENSIONS
        assert 'jpg' in service.ALLOWED_EXTENSIONS
        
        # Check unsupported extensions are not included
        assert 'exe' not in service.ALLOWED_EXTENSIONS
        assert 'zip' not in service.ALLOWED_EXTENSIONS


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""
    
    @patch('app.services.email_ingest_service.settings')
    def test_check_email_configured_false(self, mock_settings):
        """Test check_email_configured when not configured."""
        mock_settings.email_imap_host = None
        mock_settings.email_imap_user = None
        mock_settings.email_imap_password = None
        
        result = check_email_configured()
        assert result is False
    
    @patch('app.services.email_ingest_service.settings')
    def test_check_email_configured_true(self, mock_settings):
        """Test check_email_configured when configured."""
        mock_settings.email_imap_host = "imap.gmail.com"
        mock_settings.email_imap_user = "test@gmail.com"
        mock_settings.email_imap_password = "apppassword"
        mock_settings.email_imap_port = 993
        mock_settings.email_processed_folder = "Processed"
        
        result = check_email_configured()
        assert result is True


class TestMockedConnection:
    """Tests with mocked IMAP connection."""
    
    @patch('app.services.email_ingest_service.imaplib.IMAP4_SSL')
    def test_connect_success(self, mock_imap):
        """Test successful connection."""
        mock_connection = MagicMock()
        mock_imap.return_value = mock_connection
        
        service = EmailIngestService(
            host="imap.test.com",
            username="test@test.com",
            password="password123"
        )
        
        service.connect()
        
        mock_imap.assert_called_once_with("imap.test.com", 993)
        mock_connection.login.assert_called_once_with("test@test.com", "password123")
        assert service._connected is True
    
    @patch('app.services.email_ingest_service.imaplib.IMAP4_SSL')
    def test_connect_failure(self, mock_imap):
        """Test connection failure."""
        import imaplib
        mock_imap.side_effect = imaplib.IMAP4.error("Connection refused")
        
        service = EmailIngestService(
            host="imap.test.com",
            username="test@test.com",
            password="password123"
        )
        
        with pytest.raises(ConnectionError):
            service.connect()
    
    @patch('app.services.email_ingest_service.imaplib.IMAP4_SSL')
    def test_context_manager(self, mock_imap):
        """Test context manager usage."""
        mock_connection = MagicMock()
        mock_imap.return_value = mock_connection
        
        service = EmailIngestService(
            host="imap.test.com",
            username="test@test.com",
            password="password123"
        )
        
        with service:
            assert service._connected is True
        
        mock_connection.logout.assert_called_once()
    
    @patch('app.services.email_ingest_service.imaplib.IMAP4_SSL')
    def test_get_status_connected(self, mock_imap):
        """Test get_status when connected."""
        mock_connection = MagicMock()
        mock_connection.select.return_value = ("OK", [b"25"])
        mock_imap.return_value = mock_connection
        
        service = EmailIngestService(
            host="imap.test.com",
            username="test@test.com",
            password="password123"
        )
        
        with service:
            status = service.get_status()
        
        assert status["connected"] is True
        assert status["message_count"] == 25
        assert status["host"] == "imap.test.com"


# Run with: pytest app/tests/unit/test_email_ingest_service.py -v
