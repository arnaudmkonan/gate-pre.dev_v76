"""
Lead Management API Routes.

Handles lead capture from the commercial landing page for sales follow-up.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel as PydanticBaseModel, Field
from sqlalchemy import Column, String, DateTime, Text, select, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.base import BaseModel

router = APIRouter(prefix="/api/leads", tags=["leads"])


# ============================================================================
# DATABASE MODEL
# ============================================================================

class Lead(BaseModel):
    """Lead model for storing trial registrations and demo requests."""
    
    __tablename__ = "leads"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    company = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    company_size = Column(String(50), nullable=True)
    role = Column(String(100), nullable=True)
    source = Column(String(100), nullable=True)  # landing_page_trial, demo_request, etc.
    notes = Column(Text, nullable=True)
    status = Column(String(50), default="new")  # new, contacted, qualified, converted, lost
    registered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ============================================================================
# SCHEMAS
# ============================================================================

class LeadCreate(PydanticBaseModel):
    """Schema for creating a new lead."""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=255)
    company: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    company_size: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=100)
    source: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    registered_at: Optional[datetime] = None


class LeadResponse(PydanticBaseModel):
    """Schema for lead response."""
    id: UUID
    first_name: str
    last_name: str
    email: str
    company: str
    phone: Optional[str]
    company_size: Optional[str]
    role: Optional[str]
    source: Optional[str]
    status: str
    registered_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class LeadUpdate(PydanticBaseModel):
    """Schema for updating a lead."""
    status: Optional[str] = None
    notes: Optional[str] = None
    phone: Optional[str] = None
    company_size: Optional[str] = None
    role: Optional[str] = None


class LeadListResponse(PydanticBaseModel):
    """Schema for paginated lead list."""
    leads: list[LeadResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# API ROUTES
# ============================================================================

@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(lead_data: LeadCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new lead from trial registration or demo request.
    
    This endpoint accepts registrations from the commercial landing page.
    """
    # Check if email already exists
    result = await db.execute(
        select(Lead).where(Lead.email == lead_data.email)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Return existing lead instead of error (idempotent)
        return existing
    
    # Create new lead
    lead = Lead(
        id=uuid4(),
        first_name=lead_data.first_name,
        last_name=lead_data.last_name,
        email=lead_data.email,
        company=lead_data.company,
        phone=lead_data.phone,
        company_size=lead_data.company_size,
        role=lead_data.role,
        source=lead_data.source or "landing_page",
        notes=lead_data.notes,
        status="new",
        registered_at=lead_data.registered_at or datetime.now(timezone.utc),
    )
    
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    
    # Send notification email (async, non-blocking)
    try:
        await send_lead_notification(lead)
    except Exception as e:
        # Log but don't fail the request
        import logging
        logging.warning(f"Failed to send lead notification: {e}")
    
    return lead


async def send_lead_notification(lead: Lead):
    """Send email notification to sales team about new lead."""
    import os
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # Get email config from environment
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    sales_email = os.getenv("SALES_NOTIFICATION_EMAIL", "")
    
    if not all([smtp_host, smtp_user, smtp_pass, sales_email]):
        # Email not configured, skip notification
        return
    
    role_labels = {
        "customs_broker": "Customs Broker",
        "freight_forwarder": "Freight Forwarder",
        "importer": "Importer / Shipper",
        "compliance": "Trade Compliance",
        "operations": "Operations Manager",
        "it": "IT / Technology",
        "executive": "Executive / Owner",
        "other": "Other",
    }
    
    role_display = role_labels.get(lead.role, lead.role) if lead.role else "Not specified"
    
    # Compose email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 New DocuMind Trial Lead: {lead.first_name} {lead.last_name} at {lead.company}"
    msg["From"] = smtp_user
    msg["To"] = sales_email
    
    html_body = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">New Trial Registration! 🚀</h1>
        </div>
        
        <div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 12px 12px;">
            <h2 style="margin-top: 0; color: #1e293b;">Lead Details</h2>
            
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; color: #64748b; width: 120px;">Name:</td>
                    <td style="padding: 8px 0; font-weight: 600; color: #1e293b;">{lead.first_name} {lead.last_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Email:</td>
                    <td style="padding: 8px 0;"><a href="mailto:{lead.email}" style="color: #4f46e5;">{lead.email}</a></td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Company:</td>
                    <td style="padding: 8px 0; font-weight: 600; color: #1e293b;">{lead.company}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Company Size:</td>
                    <td style="padding: 8px 0; color: #1e293b;">{lead.company_size or 'Not specified'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Phone:</td>
                    <td style="padding: 8px 0; color: #1e293b;">{lead.phone or 'Not provided'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Role:</td>
                    <td style="padding: 8px 0; color: #1e293b;">{role_display}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Source:</td>
                    <td style="padding: 8px 0; color: #1e293b;">{(lead.source or 'landing_page').replace('_', ' ').title()}</td>
                </tr>
            </table>
            
            <div style="margin-top: 24px; text-align: center;">
                <a href="mailto:{lead.email}?subject=DocuMind%20-%20Welcome%20to%20your%20trial&body=Hi%20{lead.first_name},%0A%0AThank%20you%20for%20signing%20up%20for%20DocuMind!" 
                   style="display: inline-block; background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                    Contact This Lead
                </a>
            </div>
            
            <p style="margin-top: 24px; font-size: 12px; color: #94a3b8; text-align: center;">
                Registered: {lead.registered_at.strftime('%B %d, %Y at %I:%M %p UTC')}
            </p>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(html_body, "html"))
    
    # Send email
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


@router.get("", response_model=LeadListResponse)
async def list_leads(
    page: int = 1,
    page_size: int = 50,
    status_filter: Optional[str] = None,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List all leads with optional filtering.
    
    For internal sales team use.
    """
    query = select(Lead)
    
    if status_filter:
        query = query.where(Lead.status == status_filter)
    if source:
        query = query.where(Lead.source == source)
    
    # Get total count
    count_result = await db.execute(select(func.count(Lead.id)))
    total_count = count_result.scalar() or 0
    
    # Apply pagination
    query = query.order_by(Lead.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    leads = result.scalars().all()
    
    return LeadListResponse(
        leads=leads,
        total=total_count,
        page=page,
        page_size=page_size
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific lead by ID."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    return lead


@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: UUID,
    update_data: LeadUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a lead's status or notes."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    # Update fields
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    
    lead.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(lead)
    
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a lead."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    await db.delete(lead)
    await db.commit()


@router.get("/stats/summary")
async def get_lead_stats(db: AsyncSession = Depends(get_db)):
    """Get lead statistics for dashboard."""
    result = await db.execute(select(Lead))
    all_leads = result.scalars().all()
    
    total = len(all_leads)
    by_status = {}
    by_source = {}
    by_role = {}
    
    for lead in all_leads:
        # Count by status
        lead_status = lead.status or "unknown"
        by_status[lead_status] = by_status.get(lead_status, 0) + 1
        
        # Count by source
        lead_source = lead.source or "unknown"
        by_source[lead_source] = by_source.get(lead_source, 0) + 1
        
        # Count by role
        lead_role = lead.role or "unknown"
        by_role[lead_role] = by_role.get(lead_role, 0) + 1
    
    return {
        "total": total,
        "by_status": by_status,
        "by_source": by_source,
        "by_role": by_role
    }
