"""
Email Ingestion Service.

Monitors email inbox for document attachments and automatically
uploads them to the document processing pipeline.

Supports:
- IMAP connections (Gmail, Outlook, generic)
- OAuth2 for Gmail
- Attachment extraction (PDF, images, Excel)
- Auto-tagging by sender/subject
"""

import imaplib
import email
from email.header import decode_header
from email.message import Message
import logging
import tempfile
import os
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import uuid4
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailProvider(str, Enum):
    """Supported email providers."""
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    IMAP = "imap"  # Generic IMAP


@dataclass
class EmailAttachment:
    """Represents an extracted email attachment."""
    filename: str
    content_type: str
    data: bytes
    size: int


@dataclass
class EmailMessage:
    """Represents a processed email message."""
    message_id: str
    subject: str
    sender: str
    sender_email: str
    date: datetime
    attachments: List[EmailAttachment]
    body_text: Optional[str] = None
    folder: str = "INBOX"


@dataclass
class IngestionResult:
    """Result of processing an email."""
    email_id: str
    success: bool
    documents_created: int
    error: Optional[str] = None
    document_ids: List[str] = None
    
    def __post_init__(self):
        if self.document_ids is None:
            self.document_ids = []


class EmailIngestService:
    """
    Service for ingesting documents from email.
    
    Usage:
        service = EmailIngestService()
        async with service.connect():
            results = await service.process_inbox()
    """
    
    # Supported attachment types
    ALLOWED_EXTENSIONS = {
        'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'tif',
        'xlsx', 'xls', 'csv', 'doc', 'docx'
    }
    
    ALLOWED_CONTENT_TYPES = {
        'application/pdf',
        'image/png',
        'image/jpeg',
        'image/tiff',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'text/csv',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_ssl: bool = True,
        inbox_folder: Optional[str] = None,
        processed_folder: Optional[str] = None,
    ):
        """
        Initialize email ingestion service.
        
        Args:
            host: IMAP host (defaults to EMAIL_IMAP_HOST env var)
            port: IMAP port (defaults to 993 for SSL)
            username: Email username
            password: Email password
            use_ssl: Use SSL connection
            inbox_folder: Folder to monitor (defaults to EMAIL_FOLDER env var)
            processed_folder: Folder to move processed emails
        """
        self.host = host or getattr(settings, 'email_imap_host', None)
        self.port = port or getattr(settings, 'email_imap_port', 993)
        self.username = username or getattr(settings, 'email_imap_user', None)
        self.password = password or getattr(settings, 'email_imap_password', None)
        self.use_ssl = use_ssl
        self.inbox_folder = inbox_folder or getattr(settings, 'email_folder', 'INBOX')
        self.processed_folder = processed_folder or getattr(
            settings, 'email_processed_folder', 'Processed'
        )
        
        self._connection: Optional[imaplib.IMAP4_SSL] = None
        self._connected = False
    
    @property
    def is_configured(self) -> bool:
        """Check if email settings are configured."""
        return bool(self.host and self.username and self.password)
    
    def connect(self) -> 'EmailIngestService':
        """
        Connect to IMAP server.
        
        Returns context manager for connection lifecycle.
        """
        if not self.is_configured:
            raise ValueError(
                "Email not configured. Set EMAIL_IMAP_HOST, EMAIL_IMAP_USER, EMAIL_IMAP_PASSWORD"
            )
        
        try:
            if self.use_ssl:
                self._connection = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                self._connection = imaplib.IMAP4(self.host, self.port)
            
            self._connection.login(self.username, self.password)
            self._connected = True
            logger.info(f"Connected to email server: {self.host}")
            
        except imaplib.IMAP4.error as e:
            logger.error(f"Failed to connect to email server: {e}")
            raise ConnectionError(f"Email connection failed: {e}")
        
        return self
    
    def disconnect(self):
        """Disconnect from IMAP server."""
        if self._connection:
            try:
                self._connection.logout()
            except Exception as e:
                logger.warning(f"Error during logout: {e}")
            finally:
                self._connection = None
                self._connected = False
    
    def __enter__(self):
        """Context manager entry."""
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get connection status and inbox info.
        
        Returns:
            Dict with connection status, message count, etc.
        """
        if not self._connected:
            return {
                "connected": False,
                "configured": self.is_configured,
                "host": self.host,
                "error": "Not connected"
            }
        
        try:
            status, data = self._connection.select(self.inbox_folder)
            message_count = int(data[0]) if status == "OK" else 0
            
            return {
                "connected": True,
                "host": self.host,
                "username": self.username,
                "folder": self.inbox_folder,
                "message_count": message_count,
                "last_check": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }
    
    def fetch_unread_emails(
        self,
        limit: int = 50,
        since_date: Optional[datetime] = None,
        allowed_senders: Optional[List[str]] = None,
        subject_keywords: Optional[List[str]] = None,
    ) -> List[EmailMessage]:
        """
        Fetch unread emails with attachments.
        
        Args:
            limit: Maximum emails to fetch
            since_date: Only fetch emails after this date (defaults to email_lookback_days)
            allowed_senders: Only process emails from these senders (defaults to config)
            subject_keywords: Only process emails with these keywords in subject (defaults to config)
            
        Returns:
            List of EmailMessage objects with valid attachments
        """
        if not self._connected:
            raise ConnectionError("Not connected to email server")
        
        # Use config defaults if not specified
        if since_date is None:
            lookback_days = getattr(settings, 'email_lookback_days', 7)
            since_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        if allowed_senders is None:
            senders_str = getattr(settings, 'email_allowed_senders', None)
            if senders_str:
                allowed_senders = [s.strip().lower() for s in senders_str.split(',')]
        
        if subject_keywords is None:
            keywords_str = getattr(settings, 'email_subject_keywords', None)
            if keywords_str:
                subject_keywords = [k.strip().lower() for k in keywords_str.split(',')]
        
        self._connection.select(self.inbox_folder)
        
        # Build IMAP search criteria
        # SINCE date format: DD-Mon-YYYY
        date_str = since_date.strftime("%d-%b-%Y")
        search_criteria = f'(UNSEEN SINCE {date_str})'
        
        logger.info(f"Searching emails in {self.inbox_folder}: {search_criteria}")
        
        status, message_ids = self._connection.search(None, search_criteria)
        
        if status != "OK":
            logger.warning(f"Email search failed: {status}")
            return []
        
        ids = message_ids[0].split()
        logger.info(f"Found {len(ids)} unread emails since {date_str}")
        
        # Get most recent, limited
        ids = ids[-limit:] if len(ids) > limit else ids
        
        emails = []
        for msg_id in ids:
            try:
                email_msg = self._fetch_email(msg_id)
                
                if not email_msg:
                    continue
                    
                # Filter: Must have attachments
                if not email_msg.attachments:
                    continue
                
                # Filter: Sender whitelist
                if allowed_senders:
                    sender_email_lower = email_msg.sender_email.lower()
                    if not any(sender in sender_email_lower for sender in allowed_senders):
                        logger.debug(f"Skipping email from {email_msg.sender_email} - not in allowed senders")
                        continue
                
                # Filter: Subject keywords
                if subject_keywords:
                    subject_lower = email_msg.subject.lower()
                    if not any(kw in subject_lower for kw in subject_keywords):
                        logger.debug(f"Skipping email '{email_msg.subject}' - no matching keywords")
                        continue
                
                emails.append(email_msg)
                logger.info(f"Matched email: {email_msg.subject} from {email_msg.sender_email}")
                
            except Exception as e:
                logger.error(f"Error fetching email {msg_id}: {e}")
        
        logger.info(f"Returning {len(emails)} emails matching all filters")
        return emails
    
    def _fetch_email(self, msg_id: bytes) -> Optional[EmailMessage]:
        """Fetch and parse a single email."""
        status, data = self._connection.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return None
        
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        # Parse headers
        subject = self._decode_header(msg.get("Subject", ""))
        from_header = self._decode_header(msg.get("From", ""))
        date_header = msg.get("Date", "")
        message_id = msg.get("Message-ID", str(uuid4()))
        
        # Parse sender
        sender_name, sender_email = self._parse_sender(from_header)
        
        # Parse date
        try:
            date = email.utils.parsedate_to_datetime(date_header)
        except:
            date = datetime.utcnow()
        
        # Extract attachments
        attachments = self._extract_attachments(msg)
        
        # Extract body
        body_text = self._extract_body(msg)
        
        return EmailMessage(
            message_id=message_id,
            subject=subject,
            sender=sender_name,
            sender_email=sender_email,
            date=date,
            attachments=attachments,
            body_text=body_text
        )
    
    def _decode_header(self, header: str) -> str:
        """Decode email header to string."""
        if not header:
            return ""
        
        decoded_parts = decode_header(header)
        result = []
        for content, charset in decoded_parts:
            if isinstance(content, bytes):
                charset = charset or "utf-8"
                try:
                    result.append(content.decode(charset))
                except:
                    result.append(content.decode("utf-8", errors="replace"))
            else:
                result.append(content)
        
        return " ".join(result)
    
    def _parse_sender(self, from_header: str) -> Tuple[str, str]:
        """Parse sender name and email from From header."""
        import re
        
        # Handle email in angle brackets: "Name" <email@domain.com> or Name <email@domain.com>
        match = re.match(r'"?([^"<]*)"?\s*<([^>]+)>', from_header)
        if match:
            name = match.group(1).strip()
            email_addr = match.group(2).strip()
            return name or email_addr, email_addr
        
        # Handle plain email without angle brackets
        if '@' in from_header and '<' not in from_header:
            email_addr = from_header.strip()
            return email_addr, email_addr
        
        return from_header, from_header
    
    def _extract_attachments(self, msg: Message) -> List[EmailAttachment]:
        """Extract valid attachments from email."""
        attachments = []
        
        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")
            
            if "attachment" not in content_disposition:
                continue
            
            filename = part.get_filename()
            if not filename:
                continue
            
            filename = self._decode_header(filename)
            
            # Check extension
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            if ext not in self.ALLOWED_EXTENSIONS:
                logger.debug(f"Skipping unsupported file: {filename}")
                continue
            
            content_type = part.get_content_type()
            data = part.get_payload(decode=True)
            
            if data:
                attachments.append(EmailAttachment(
                    filename=filename,
                    content_type=content_type,
                    data=data,
                    size=len(data)
                ))
        
        return attachments
    
    def _extract_body(self, msg: Message) -> Optional[str]:
        """Extract plain text body from email."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
        else:
            if msg.get_content_type() == "text/plain":
                payload = msg.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")
        
        return None
    
    def mark_as_processed(self, msg_id: str):
        """
        Mark email as processed by moving to processed folder.
        
        Args:
            msg_id: Message ID to mark
        """
        if not self._connected:
            return
        
        try:
            # Create processed folder if it doesn't exist
            self._connection.create(self.processed_folder)
        except:
            pass  # Folder may already exist
        
        try:
            # Copy to processed folder
            self._connection.copy(msg_id.encode(), self.processed_folder)
            # Mark original as deleted
            self._connection.store(msg_id.encode(), '+FLAGS', '\\Deleted')
            # Expunge deleted messages
            self._connection.expunge()
            logger.debug(f"Marked email {msg_id} as processed")
        except Exception as e:
            logger.warning(f"Failed to move email to processed: {e}")
    
    def save_attachment_temp(self, attachment: EmailAttachment) -> str:
        """
        Save attachment to temp file.
        
        Returns:
            Path to temp file
        """
        suffix = os.path.splitext(attachment.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(attachment.data)
            return f.name


# Convenience functions

def check_email_configured() -> bool:
    """Check if email ingestion is configured."""
    service = EmailIngestService()
    return service.is_configured


def get_email_status() -> Dict[str, Any]:
    """Get email connection status."""
    service = EmailIngestService()
    
    if not service.is_configured:
        return {
            "configured": False,
            "connected": False,
            "message": "Email not configured. Set EMAIL_IMAP_* environment variables."
        }
    
    try:
        with service:
            return service.get_status()
    except Exception as e:
        return {
            "configured": True,
            "connected": False,
            "error": str(e)
        }
