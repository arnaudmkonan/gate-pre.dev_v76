"""
GATE Platform — Email Delivery Service.

Handles outbound email sending for all platform notifications:
- Password reset links
- User invitations
- Document request notifications
- Entry status updates
- Compliance alerts

When SMTP is not configured, emails are logged to console (dev mode).
"""
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, List, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# HTML templates (inline for simplicity — can be moved to files later)
BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #f4f7fa; }}
  .container {{ max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow: hidden; }}
  .header {{ background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%); padding: 30px; text-align: center; }}
  .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; font-weight: 600; }}
  .header p {{ color: #bbdefb; margin: 5px 0 0; font-size: 14px; }}
  .body {{ padding: 30px; }}
  .body p {{ color: #37474f; line-height: 1.6; margin: 12px 0; }}
  .btn {{ display: inline-block; background: #1565c0; color: #ffffff !important; padding: 12px 28px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 16px 0; }}
  .btn:hover {{ background: #0d47a1; }}
  .footer {{ padding: 20px 30px; background: #f8f9fa; text-align: center; color: #78909c; font-size: 12px; }}
  .code {{ background: #e8eaf6; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 14px; }}
  .info-box {{ background: #e3f2fd; border-left: 4px solid #1565c0; padding: 12px 16px; border-radius: 4px; margin: 16px 0; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>{brand_name}</h1>
      <p>Customs Brokerage &amp; Trade Compliance</p>
    </div>
    <div class="body">
      {content}
    </div>
    <div class="footer">
      <p>This email was sent by {brand_name}. Do not reply to this email.</p>
      <p>&copy; 2026 {brand_name}. All rights reserved.</p>
    </div>
  </div>
</body>
</html>
"""


def _render_email_html(content: str) -> str:
    brand = (settings.broker_name or "Customs Brokerage").strip()
    return BASE_TEMPLATE.format(content=content, brand_name=brand)


class EmailService:
    """Unified outbound email sending for the GATE platform."""

    def __init__(self):
        self.smtp_configured = bool(
            settings.smtp_host
            and settings.smtp_username
        )
        if not self.smtp_configured:
            logger.info("SMTP not configured — emails will be logged to console")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """
        Send an email.

        Returns True if sent successfully, False otherwise.
        When SMTP is not configured, logs the email content and returns True.
        """
        if not self.smtp_configured:
            logger.info(
                f"\n{'='*60}\n"
                f"📧 EMAIL (dev mode — SMTP not configured)\n"
                f"{'='*60}\n"
                f"To:      {to_email}\n"
                f"Reply-To:{reply_to or '(default)'}\n"
                f"Subject: {subject}\n"
                f"{'─'*60}\n"
                f"{text_content or 'See HTML content'}\n"
                f"{'='*60}\n"
            )
            return True

        try:
            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["From"] = f"{settings.smtp_from_email}"
            msg["To"] = to_email
            msg["Subject"] = subject
            if reply_to:
                msg["Reply-To"] = reply_to

            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port or 587,
                username=settings.smtp_username,
                password=settings.smtp_password,
                use_tls=settings.smtp_tls,
            )
            logger.info(f"Email sent to {to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    # =========================================================================
    # Pre-built email types
    # =========================================================================

    async def send_password_reset(
        self,
        to_email: str,
        reset_token: str,
        reset_url: Optional[str] = None,
    ) -> bool:
        """Send password reset email."""
        # Build reset URL
        if not reset_url:
            reset_url = f"{settings.public_app_url}/reset-password?token={reset_token}"

        content = f"""
        <p>Hello,</p>
        <p>We received a request to reset your password. Click the button below to set a new password:</p>
        <p style="text-align: center;">
            <a href="{reset_url}" class="btn">Reset Password</a>
        </p>
        <p>Or copy this link into your browser:</p>
        <p class="code">{reset_url}</p>
        <p>This link expires in 1 hour. If you didn't request a password reset, you can safely ignore this email.</p>
        """

        text = (
            f"Password Reset Request\n\n"
            f"Visit this link to reset your password:\n{reset_url}\n\n"
            f"This link expires in 1 hour."
        )

        brand = (settings.broker_name or "Customs Brokerage").strip()
        return await self.send_email(
            to_email=to_email,
            subject=f"{brand} — Password Reset",
            html_content=_render_email_html(content),
            text_content=text,
        )

    async def send_email_verification(
        self,
        to_email: str,
        verify_token: str,
        user_name: Optional[str] = None,
    ) -> bool:
        brand = (settings.broker_name or "Customs Brokerage").strip()
        verify_url = f"{settings.public_app_url}/verify-email?token={verify_token}"
        greeting = f"Hello {user_name}," if user_name else "Hello,"
        content = f"""
        <p>{greeting}</p>
        <p>Confirm your email to activate your {brand} account:</p>
        <p style="text-align: center;">
            <a href="{verify_url}" class="btn">Verify Email</a>
        </p>
        <p>Or copy this link:</p>
        <p class="code">{verify_url}</p>
        """
        text = f"Verify your {brand} account:\n{verify_url}\n"
        return await self.send_email(
            to_email=to_email,
            subject=f"{brand} — Verify your email",
            html_content=_render_email_html(content),
            text_content=text,
        )

    async def send_invitation(
        self,
        to_email: str,
        inviter_name: str,
        client_name: str,
        invitation_token: str,
        invitation_url: Optional[str] = None,
    ) -> bool:
        """Send user invitation email."""
        brand = (settings.broker_name or "Customs Brokerage").strip()
        if not invitation_url:
            invitation_url = f"{settings.public_app_url}/register?token={invitation_token}"

        content = f"""
        <p>Hello,</p>
        <p><strong>{inviter_name}</strong> has invited you to join <strong>{client_name}</strong> on {brand}.</p>
        <div class="info-box">
            <strong>{brand}</strong> streamlines trade document intake, duty calculation, and customs entry preparation.
        </div>
        <p style="text-align: center;">
            <a href="{invitation_url}" class="btn">Accept Invitation</a>
        </p>
        <p>Or copy this link: <span class="code">{invitation_url}</span></p>
        <p>This invitation expires in 7 days.</p>
        """

        text = (
            f"You've been invited to {brand}\n\n"
            f"{inviter_name} has invited you to join {client_name}.\n"
            f"Accept here: {invitation_url}\n\n"
            f"This invitation expires in 7 days."
        )

        return await self.send_email(
            to_email=to_email,
            subject=f"{brand} — Invitation from {client_name}",
            html_content=_render_email_html(content),
            text_content=text,
        )

    async def send_entry_status_update(
        self,
        to_email: str,
        entry_number: str,
        old_status: str,
        new_status: str,
        entry_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Send entry status change notification."""
        status_colors = {
            "accepted": "#2e7d32",
            "rejected": "#c62828",
            "released": "#1565c0",
            "liquidated": "#6a1b9a",
            "filed": "#e65100",
        }
        color = status_colors.get(new_status.lower(), "#37474f")

        content = f"""
        <p>Hello,</p>
        <p>Entry <strong>{entry_number}</strong> has been updated:</p>
        <div class="info-box">
            <p>Status: <strong style="color:{color}">{new_status.upper()}</strong></p>
            <p>Previous: {old_status}</p>
            {f'<p>Notes: {notes}</p>' if notes else ''}
        </div>
        {f'<p style="text-align:center;"><a href="{entry_url}" class="btn">View Entry</a></p>' if entry_url else ''}
        """

        text = (
            f"Entry {entry_number} Status Update\n\n"
            f"New Status: {new_status}\n"
            f"Previous: {old_status}\n"
            f"{f'Notes: {notes}' if notes else ''}"
        )

        brand = (settings.broker_name or "Customs Brokerage").strip()
        return await self.send_email(
            to_email=to_email,
            subject=f"{brand} — Entry {entry_number}: {new_status.upper()}",
            html_content=_render_email_html(content),
            text_content=text,
        )

    async def send_document_request(
        self,
        to_email: str,
        requester_name: str,
        document_types: List[str],
        entry_number: Optional[str] = None,
        message: Optional[str] = None,
        upload_url: Optional[str] = None,
        shipment_id: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """Send document request to client.

        When ``shipment_id`` is set, the subject includes ``[GATE-DOCREQ:{id}]`` so
        IMAP inbox replies with attachments can be auto-linked back to that shipment.
        """
        brand = (settings.broker_name or "Customs Brokerage").strip()
        doc_list = "".join(f"<li>{dt}</li>" for dt in document_types)
        corr = f"[GATE-DOCREQ:{shipment_id}]" if shipment_id else ""
        reply_hint = (
            "<p><em>Reply to this email with the document attached</em> — "
            "attachments are ingested automatically when our inbox monitor is enabled.</p>"
            if reply_to
            else ""
        )

        content = f"""
        <p>Hello,</p>
        <p><strong>{requester_name}</strong> has requested the following documents
        {f'for shipment/entry <strong>{entry_number}</strong>' if entry_number else ''}:</p>
        <ul>{doc_list}</ul>
        {f'<div class="info-box"><p>{message}</p></div>' if message else ''}
        {reply_hint}
        {f'<p style="text-align:center;"><a href="{upload_url}" class="btn">Upload Documents</a></p>' if upload_url else ''}
        {f'<p style="color:#888;font-size:12px;">Ref {corr}</p>' if corr else ''}
        """

        text = (
            f"Document Request from {requester_name}\n\n"
            f"Documents needed: {', '.join(document_types)}\n"
            f"{f'For shipment/entry: {entry_number}' if entry_number else ''}\n"
            f"{f'Message: {message}' if message else ''}\n"
            f"{'Reply with the file attached for automatic processing.' if reply_to else ''}\n"
            f"{corr}"
        )

        subject = f"{brand} — Document Request{f' for {entry_number}' if entry_number else ''}"
        if corr:
            subject = f"{subject} {corr}"

        return await self.send_email(
            to_email=to_email,
            subject=subject,
            html_content=_render_email_html(content),
            text_content=text,
            reply_to=reply_to,
        )

    async def send_compliance_alert(
        self,
        to_email: str,
        alert_type: str,
        entry_number: Optional[str] = None,
        details: Optional[str] = None,
    ) -> bool:
        """Send compliance alert notification."""
        brand = (settings.broker_name or "Customs Brokerage").strip()
        content = f"""
        <p>Hello,</p>
        <p>A compliance alert has been triggered:</p>
        <div class="info-box" style="border-left-color: #c62828;">
            <p><strong>Alert: {alert_type}</strong></p>
            {f'<p>Entry: {entry_number}</p>' if entry_number else ''}
            {f'<p>{details}</p>' if details else ''}
        </div>
        <p>Please review this alert and take appropriate action.</p>
        """

        text = (
            f"Compliance Alert: {alert_type}\n\n"
            f"{f'Entry: {entry_number}' if entry_number else ''}\n"
            f"{f'Details: {details}' if details else ''}"
        )

        return await self.send_email(
            to_email=to_email,
            subject=f"{brand} — Compliance Alert: {alert_type}",
            html_content=_render_email_html(content),
            text_content=text,
        )


# Singleton instance
email_service = EmailService()
