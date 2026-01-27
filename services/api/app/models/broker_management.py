"""
Broker License, Permit & Bond Management Model.

Tracks:
- Broker license numbers and renewal dates
- Port permits (which ports broker can file at)
- Continuous bonds (CB) for high-volume importers
- Single transaction bonds (STB) for one-time entries
- Bond sufficiency and expiration warnings

Task 3.7 from ROADMAP_FULL_WORKFLOW.md
"""
from enum import Enum
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, DateTime, Date, ForeignKey, Integer, Text, Boolean, Index, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.models.base import BaseModel


class BondType(str, Enum):
    """Types of customs bonds."""
    CONTINUOUS = "continuous"  # Activity Code 1 - Continuous entry bond
    SINGLE_TRANSACTION = "single_transaction"  # Activity Code 8 - Single entry bond
    DRAWBACK = "drawback"  # Activity Code 4 - Drawback bond
    FOREIGN_TRADE_ZONE = "ftz"  # Activity Code 6 - FTZ bond
    INTERNATIONAL_CARRIER = "carrier"  # Activity Code 3 - International carrier bond
    CUSTODIAN = "custodian"  # Activity Code 9 - Customs warehouse/bonded carrier


class BondStatus(str, Enum):
    """Bond status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"
    CANCELLED = "cancelled"
    EXHAUSTED = "exhausted"  # For STB - fully used


class LicenseStatus(str, Enum):
    """Broker license status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING_RENEWAL = "pending_renewal"


class BrokerLicense(BaseModel):
    """
    Customs Broker License.
    
    Tracks broker license numbers, status, and renewal information.
    A broker may have multiple licenses for different districts.
    """
    __tablename__ = "broker_licenses"
    
    # License identification
    license_number = Column(String(20), unique=True, nullable=False, index=True)
    filer_code = Column(String(10), nullable=True, index=True)  # 3-character filer code
    
    # Broker information
    broker_name = Column(String(500), nullable=False)
    broker_type = Column(String(50), nullable=True)  # individual, partnership, corporation
    
    # Status
    status = Column(String(20), default=LicenseStatus.ACTIVE.value, nullable=False)
    
    # Dates
    issue_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    last_renewal_date = Column(Date, nullable=True)
    
    # District/Port information
    issuing_district = Column(String(10), nullable=True)  # CBP district code
    permitted_ports = Column(ARRAY(String), nullable=True, default=[])  # Port codes
    
    # Contact
    primary_contact = Column(String(200), nullable=True)
    contact_email = Column(String(200), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    
    # Compliance
    exam_pass_date = Column(Date, nullable=True)
    triennial_status_report_due = Column(Date, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    permits = relationship("BrokerPortPermit", back_populates="license", cascade="all, delete-orphan")
    bonds = relationship("BrokerBond", back_populates="license")
    
    __table_args__ = (
        Index("ix_broker_licenses_status", "status"),
        Index("ix_broker_licenses_expiration", "expiration_date"),
    )
    
    def is_expiring_soon(self, days: int = 30) -> bool:
        """Check if license expires within given days."""
        if not self.expiration_date:
            return False
        remaining = (self.expiration_date - date.today()).days
        return 0 < remaining <= days
    
    def days_until_expiration(self) -> int:
        """Get days until expiration."""
        if not self.expiration_date:
            return -1
        return (self.expiration_date - date.today()).days
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "license_number": self.license_number,
            "filer_code": self.filer_code,
            "broker_name": self.broker_name,
            "broker_type": self.broker_type,
            "status": self.status,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "issuing_district": self.issuing_district,
            "permitted_ports": self.permitted_ports or [],
            "primary_contact": self.primary_contact,
            "contact_email": self.contact_email,
            "days_until_expiration": self.days_until_expiration(),
            "is_expiring_soon": self.is_expiring_soon(),
            "triennial_status_report_due": self.triennial_status_report_due.isoformat() if self.triennial_status_report_due else None,
        }


class BrokerPortPermit(BaseModel):
    """
    Port Permit for a broker license.
    
    Brokers need permits for each port they file at.
    """
    __tablename__ = "broker_port_permits"
    
    license_id = Column(UUID(as_uuid=True), ForeignKey("broker_licenses.id", ondelete="CASCADE"), nullable=False)
    
    # Port info
    port_code = Column(String(10), nullable=False, index=True)
    port_name = Column(String(100), nullable=True)
    district_code = Column(String(10), nullable=True)
    
    # Status
    status = Column(String(20), default="active", nullable=False)
    
    # Dates
    issue_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    
    # Relationship
    license = relationship("BrokerLicense", back_populates="permits")
    
    __table_args__ = (
        Index("ix_broker_port_permits_license", "license_id"),
        Index("ix_broker_port_permits_port", "port_code"),
    )
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "port_code": self.port_code,
            "port_name": self.port_name,
            "district_code": self.district_code,
            "status": self.status,
            "issue_date": self.issue_date.isoformat() if self.issue_date else None,
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
        }


class BrokerBond(BaseModel):
    """
    Customs Bond for entries.
    
    Types:
    - Continuous Bond (CB): Covers multiple entries over a year
    - Single Transaction Bond (STB): Covers one specific entry
    
    Bond sufficiency is typically 10% of total duties paid in prior year
    (minimum $50,000 for continuous bonds).
    """
    __tablename__ = "broker_bonds"
    
    # Bond identification
    bond_number = Column(String(50), unique=True, nullable=False, index=True)
    
    # Type
    bond_type = Column(String(30), default=BondType.CONTINUOUS.value, nullable=False)
    activity_code = Column(String(5), nullable=True)  # CBP activity code (1, 3, 4, 6, 8, 9)
    
    # Status
    status = Column(String(20), default=BondStatus.ACTIVE.value, nullable=False)
    
    # Surety information
    surety_code = Column(String(10), nullable=True, index=True)  # 3-digit surety code
    surety_name = Column(String(200), nullable=True)
    
    # Bond amounts
    bond_amount = Column(Numeric(15, 2), nullable=False)  # Total bond coverage
    used_amount = Column(Numeric(15, 2), default=0)  # For STB tracking
    remaining_amount = Column(Numeric(15, 2), nullable=True)  # Calculated
    
    # For linked bonds
    license_id = Column(UUID(as_uuid=True), ForeignKey("broker_licenses.id"), nullable=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)
    
    # Principal (importer)
    principal_name = Column(String(500), nullable=True)
    principal_ior_number = Column(String(50), nullable=True)
    
    # Dates
    effective_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    termination_date = Column(Date, nullable=True)
    
    # Entry linking (for STB)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id"), nullable=True)
    entry_number = Column(String(20), nullable=True)
    
    # Coverage ports (blank = all ports)
    covered_ports = Column(ARRAY(String), nullable=True)
    
    # Rider/amendments
    rider_count = Column(Integer, default=0)
    last_rider_date = Column(Date, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    license = relationship("BrokerLicense", back_populates="bonds")
    client = relationship("Client", foreign_keys=[client_id])
    entry = relationship("Entry", foreign_keys=[entry_id])
    
    __table_args__ = (
        Index("ix_broker_bonds_status", "status"),
        Index("ix_broker_bonds_expiration", "expiration_date"),
        Index("ix_broker_bonds_type", "bond_type"),
        Index("ix_broker_bonds_surety", "surety_code"),
        Index("ix_broker_bonds_client", "client_id"),
    )
    
    def is_expiring_soon(self, days: int = 30) -> bool:
        """Check if bond expires within given days."""
        if not self.expiration_date:
            return False
        remaining = (self.expiration_date - date.today()).days
        return 0 < remaining <= days
    
    def days_until_expiration(self) -> int:
        """Get days until expiration."""
        if not self.expiration_date:
            return -1
        return (self.expiration_date - date.today()).days
    
    def calculate_remaining(self) -> Decimal:
        """Calculate remaining bond amount."""
        return Decimal(str(self.bond_amount or 0)) - Decimal(str(self.used_amount or 0))
    
    def is_sufficient(self, entry_value: Decimal) -> bool:
        """Check if bond has sufficient coverage for an entry."""
        if self.bond_type == BondType.SINGLE_TRANSACTION.value:
            return self.calculate_remaining() >= entry_value
        # Continuous bonds are evaluated annually
        return True
    
    def get_sufficiency_warning(self, annual_duty_estimate: Decimal = None) -> dict:
        """
        Check bond sufficiency.
        
        For continuous bonds: Should be 10% of estimated annual duties
        Minimum continuous bond: $50,000
        """
        if self.bond_type != BondType.CONTINUOUS.value:
            return {"sufficient": True, "warning": None}
        
        if not annual_duty_estimate:
            return {"sufficient": True, "warning": None}
        
        recommended = max(Decimal("50000"), annual_duty_estimate * Decimal("0.1"))
        
        if self.bond_amount < recommended:
            shortfall = recommended - self.bond_amount
            return {
                "sufficient": False,
                "warning": f"Bond may be insufficient. Current: ${self.bond_amount:,.2f}, Recommended: ${recommended:,.2f}",
                "current_amount": float(self.bond_amount),
                "recommended_amount": float(recommended),
                "shortfall": float(shortfall),
            }
        
        return {"sufficient": True, "warning": None}
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "bond_number": self.bond_number,
            "bond_type": self.bond_type,
            "activity_code": self.activity_code,
            "status": self.status,
            "surety_code": self.surety_code,
            "surety_name": self.surety_name,
            "bond_amount": float(self.bond_amount) if self.bond_amount else 0,
            "used_amount": float(self.used_amount) if self.used_amount else 0,
            "remaining_amount": float(self.calculate_remaining()),
            "principal_name": self.principal_name,
            "principal_ior_number": self.principal_ior_number,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiration_date": self.expiration_date.isoformat() if self.expiration_date else None,
            "days_until_expiration": self.days_until_expiration(),
            "is_expiring_soon": self.is_expiring_soon(),
            "covered_ports": self.covered_ports or [],
            "client_id": str(self.client_id) if self.client_id else None,
            "entry_id": str(self.entry_id) if self.entry_id else None,
            "entry_number": self.entry_number,
        }


# Common US surety companies
SURETY_CODES = {
    "001": "American Home Assurance Company",
    "002": "Federal Insurance Company",
    "003": "Great American Insurance Company",
    "004": "Liberty Mutual Insurance Company",
    "005": "National Union Fire Insurance",
    "006": "St. Paul Fire and Marine Insurance",
    "007": "Travelers Casualty and Surety",
    "008": "Zurich American Insurance Company",
    "009": "CNA Surety",
    "010": "Hartford Fire Insurance Company",
}


# CBP bond activity codes
BOND_ACTIVITY_CODES = {
    "1": "Importer or Broker (Continuous)",
    "2": "Custodian of Bonded Merchandise",
    "3": "International Carrier",
    "4": "Foreign Trade Zone Operator",
    "5": "Public Gauger",
    "6": "Foreign Trade Zone Activity",
    "7": "Bill of Lading",
    "8": "Single Transaction",
    "9": "Drawback",
    "10": "Team Driver",
}
