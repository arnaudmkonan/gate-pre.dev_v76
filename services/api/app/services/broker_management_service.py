"""
Broker License, Permit & Bond Management Service.

Handles:
- License CRUD and renewal tracking
- Port permit management
- Bond creation and tracking
- Sufficiency warnings
- Expiration alerts

Task 3.7 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.broker_management import (
    BrokerLicense, BrokerPortPermit, BrokerBond,
    BondType, BondStatus, LicenseStatus,
    SURETY_CODES, BOND_ACTIVITY_CODES
)


class BrokerManagementService:
    """Service for managing broker licenses, permits, and bonds."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== License Management ====================
    
    async def create_license(self, data: Dict[str, Any]) -> BrokerLicense:
        """Create a new broker license."""
        license = BrokerLicense(
            license_number=data.get("license_number"),
            filer_code=data.get("filer_code"),
            broker_name=data.get("broker_name"),
            broker_type=data.get("broker_type"),
            status=data.get("status", LicenseStatus.ACTIVE.value),
            issue_date=self._parse_date(data.get("issue_date")),
            expiration_date=self._parse_date(data.get("expiration_date")),
            issuing_district=data.get("issuing_district"),
            permitted_ports=data.get("permitted_ports", []),
            primary_contact=data.get("primary_contact"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            address=data.get("address"),
            exam_pass_date=self._parse_date(data.get("exam_pass_date")),
            triennial_status_report_due=self._parse_date(data.get("triennial_status_report_due")),
            notes=data.get("notes"),
        )
        
        self.db.add(license)
        await self.db.commit()
        await self.db.refresh(license)
        
        return license
    
    async def get_license(self, license_id: UUID) -> Optional[BrokerLicense]:
        """Get license by ID."""
        query = (
            select(BrokerLicense)
            .options(selectinload(BrokerLicense.permits))
            .where(BrokerLicense.id == license_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_license_by_number(self, license_number: str) -> Optional[BrokerLicense]:
        """Get license by license number."""
        query = select(BrokerLicense).where(BrokerLicense.license_number == license_number)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_licenses(
        self,
        status: Optional[str] = None,
        expiring_within_days: Optional[int] = None,
    ) -> List[BrokerLicense]:
        """List all licenses with optional filtering."""
        query = select(BrokerLicense).options(selectinload(BrokerLicense.permits))
        
        if status:
            query = query.where(BrokerLicense.status == status)
        
        if expiring_within_days:
            cutoff_date = date.today() + timedelta(days=expiring_within_days)
            query = query.where(
                and_(
                    BrokerLicense.expiration_date != None,
                    BrokerLicense.expiration_date <= cutoff_date,
                    BrokerLicense.expiration_date > date.today()
                )
            )
        
        query = query.order_by(BrokerLicense.broker_name)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_license(self, license_id: UUID, data: Dict[str, Any]) -> BrokerLicense:
        """Update a license."""
        license = await self.get_license(license_id)
        if not license:
            raise ValueError(f"License {license_id} not found")
        
        updatable_fields = [
            'filer_code', 'broker_name', 'broker_type', 'status',
            'issue_date', 'expiration_date', 'issuing_district', 'permitted_ports',
            'primary_contact', 'contact_email', 'contact_phone', 'address',
            'triennial_status_report_due', 'notes'
        ]
        
        for field in updatable_fields:
            if field in data:
                value = data[field]
                if field in ['issue_date', 'expiration_date', 'triennial_status_report_due']:
                    value = self._parse_date(value)
                setattr(license, field, value)
        
        await self.db.commit()
        await self.db.refresh(license)
        
        return license
    
    async def renew_license(self, license_id: UUID, new_expiration: date) -> BrokerLicense:
        """Renew a license with new expiration date."""
        license = await self.get_license(license_id)
        if not license:
            raise ValueError(f"License {license_id} not found")
        
        license.last_renewal_date = date.today()
        license.expiration_date = new_expiration
        license.status = LicenseStatus.ACTIVE.value
        
        await self.db.commit()
        await self.db.refresh(license)
        
        return license
    
    # ==================== Port Permit Management ====================
    
    async def add_port_permit(
        self,
        license_id: UUID,
        port_code: str,
        port_name: Optional[str] = None,
        district_code: Optional[str] = None,
    ) -> BrokerPortPermit:
        """Add a port permit to a license."""
        permit = BrokerPortPermit(
            license_id=license_id,
            port_code=port_code,
            port_name=port_name,
            district_code=district_code,
            status="active",
            issue_date=date.today(),
        )
        
        self.db.add(permit)
        await self.db.commit()
        await self.db.refresh(permit)
        
        return permit
    
    async def get_permits_for_license(self, license_id: UUID) -> List[BrokerPortPermit]:
        """Get all port permits for a license."""
        query = select(BrokerPortPermit).where(BrokerPortPermit.license_id == license_id)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def check_port_permit(self, license_id: UUID, port_code: str) -> bool:
        """Check if a license has permit for a specific port."""
        query = select(BrokerPortPermit).where(
            and_(
                BrokerPortPermit.license_id == license_id,
                BrokerPortPermit.port_code == port_code,
                BrokerPortPermit.status == "active"
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    # ==================== Bond Management ====================
    
    async def create_bond(self, data: Dict[str, Any]) -> BrokerBond:
        """Create a new bond."""
        bond = BrokerBond(
            bond_number=data.get("bond_number"),
            bond_type=data.get("bond_type", BondType.CONTINUOUS.value),
            activity_code=data.get("activity_code", "1"),
            status=data.get("status", BondStatus.ACTIVE.value),
            surety_code=data.get("surety_code"),
            surety_name=data.get("surety_name") or SURETY_CODES.get(data.get("surety_code", ""), ""),
            bond_amount=Decimal(str(data.get("bond_amount", 0))),
            used_amount=Decimal("0"),
            license_id=UUID(data["license_id"]) if data.get("license_id") else None,
            client_id=UUID(data["client_id"]) if data.get("client_id") else None,
            principal_name=data.get("principal_name"),
            principal_ior_number=data.get("principal_ior_number"),
            effective_date=self._parse_date(data.get("effective_date")),
            expiration_date=self._parse_date(data.get("expiration_date")),
            covered_ports=data.get("covered_ports", []),
            notes=data.get("notes"),
        )
        
        self.db.add(bond)
        await self.db.commit()
        await self.db.refresh(bond)
        
        return bond
    
    async def get_bond(self, bond_id: UUID) -> Optional[BrokerBond]:
        """Get bond by ID."""
        query = select(BrokerBond).where(BrokerBond.id == bond_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_bond_by_number(self, bond_number: str) -> Optional[BrokerBond]:
        """Get bond by bond number."""
        query = select(BrokerBond).where(BrokerBond.bond_number == bond_number)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_bonds(
        self,
        bond_type: Optional[str] = None,
        status: Optional[str] = None,
        client_id: Optional[UUID] = None,
        expiring_within_days: Optional[int] = None,
    ) -> List[BrokerBond]:
        """List bonds with optional filtering."""
        query = select(BrokerBond)
        
        conditions = []
        
        if bond_type:
            conditions.append(BrokerBond.bond_type == bond_type)
        
        if status:
            conditions.append(BrokerBond.status == status)
        
        if client_id:
            conditions.append(BrokerBond.client_id == client_id)
        
        if expiring_within_days:
            cutoff_date = date.today() + timedelta(days=expiring_within_days)
            conditions.append(
                and_(
                    BrokerBond.expiration_date != None,
                    BrokerBond.expiration_date <= cutoff_date,
                    BrokerBond.expiration_date > date.today()
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(BrokerBond.expiration_date)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_bond(self, bond_id: UUID, data: Dict[str, Any]) -> BrokerBond:
        """Update a bond."""
        bond = await self.get_bond(bond_id)
        if not bond:
            raise ValueError(f"Bond {bond_id} not found")
        
        updatable_fields = [
            'status', 'surety_code', 'surety_name', 'bond_amount',
            'principal_name', 'principal_ior_number', 'expiration_date',
            'covered_ports', 'notes'
        ]
        
        for field in updatable_fields:
            if field in data:
                value = data[field]
                if field == 'expiration_date':
                    value = self._parse_date(value)
                elif field == 'bond_amount':
                    value = Decimal(str(value))
                setattr(bond, field, value)
        
        await self.db.commit()
        await self.db.refresh(bond)
        
        return bond
    
    async def use_bond(self, bond_id: UUID, amount: Decimal, entry_number: str = None) -> BrokerBond:
        """Record usage of a bond (for STB tracking)."""
        bond = await self.get_bond(bond_id)
        if not bond:
            raise ValueError(f"Bond {bond_id} not found")
        
        bond.used_amount = Decimal(str(bond.used_amount or 0)) + amount
        bond.remaining_amount = bond.calculate_remaining()
        
        if entry_number:
            bond.entry_number = entry_number
        
        # Check if exhausted (for STB)
        if bond.bond_type == BondType.SINGLE_TRANSACTION.value:
            if bond.remaining_amount <= 0:
                bond.status = BondStatus.EXHAUSTED.value
        
        await self.db.commit()
        await self.db.refresh(bond)
        
        return bond
    
    async def get_active_bond_for_client(
        self,
        client_id: UUID,
        bond_type: str = BondType.CONTINUOUS.value,
    ) -> Optional[BrokerBond]:
        """Get active bond for a client."""
        query = select(BrokerBond).where(
            and_(
                BrokerBond.client_id == client_id,
                BrokerBond.bond_type == bond_type,
                BrokerBond.status == BondStatus.ACTIVE.value,
                or_(
                    BrokerBond.expiration_date == None,
                    BrokerBond.expiration_date > date.today()
                )
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    # ==================== Warnings & Alerts ====================
    
    async def get_expiration_warnings(self, days: int = 30) -> Dict[str, Any]:
        """Get all items expiring within given days."""
        # Licenses expiring
        licenses = await self.list_licenses(expiring_within_days=days)
        
        # Bonds expiring
        bonds = await self.list_bonds(expiring_within_days=days, status=BondStatus.ACTIVE.value)
        
        return {
            "licenses_expiring": [l.to_dict() for l in licenses],
            "licenses_count": len(licenses),
            "bonds_expiring": [b.to_dict() for b in bonds],
            "bonds_count": len(bonds),
            "days_checked": days,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def check_bond_sufficiency(
        self,
        bond_id: UUID,
        annual_duty_estimate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Check if a bond has sufficient coverage."""
        bond = await self.get_bond(bond_id)
        if not bond:
            return {"error": "Bond not found"}
        
        if annual_duty_estimate:
            return bond.get_sufficiency_warning(Decimal(str(annual_duty_estimate)))
        
        return {"sufficient": True, "warning": None}
    
    async def validate_for_entry(
        self,
        entry_value: float,
        client_id: Optional[UUID] = None,
        port_code: Optional[str] = None,
        license_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Validate that broker can file entry.
        
        Checks:
        - License is active
        - Has permit for port (if specified)
        - Bond is sufficient (if continuous) or available (if STB)
        """
        issues = []
        warnings = []
        
        # Check license
        if license_id:
            license = await self.get_license(license_id)
            if not license:
                issues.append("Broker license not found")
            elif license.status != LicenseStatus.ACTIVE.value:
                issues.append(f"License is not active (status: {license.status})")
            elif license.is_expiring_soon(7):
                warnings.append(f"License expires in {license.days_until_expiration()} days")
            
            # Check port permit
            if port_code and license:
                has_permit = await self.check_port_permit(license_id, port_code)
                if not has_permit:
                    issues.append(f"No active permit for port {port_code}")
        
        # Check bond
        if client_id:
            bond = await self.get_active_bond_for_client(client_id)
            if not bond:
                issues.append("No active bond found for client")
            else:
                if bond.is_expiring_soon(7):
                    warnings.append(f"Bond expires in {bond.days_until_expiration()} days")
                
                if bond.bond_type == BondType.SINGLE_TRANSACTION.value:
                    if not bond.is_sufficient(Decimal(str(entry_value))):
                        issues.append("Insufficient bond coverage for entry value")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "can_file": len(issues) == 0,
        }
    
    # ==================== Statistics ====================
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get broker management statistics."""
        # License stats
        license_query = select(
            BrokerLicense.status,
            func.count(BrokerLicense.id).label("count")
        ).group_by(BrokerLicense.status)
        license_result = await self.db.execute(license_query)
        license_stats = {row.status: row.count for row in license_result}
        
        # Bond stats
        bond_query = select(
            BrokerBond.bond_type,
            BrokerBond.status,
            func.count(BrokerBond.id).label("count"),
            func.sum(BrokerBond.bond_amount).label("total_amount")
        ).group_by(BrokerBond.bond_type, BrokerBond.status)
        bond_result = await self.db.execute(bond_query)
        bond_stats = [
            {
                "type": row.bond_type,
                "status": row.status,
                "count": row.count,
                "total_amount": float(row.total_amount or 0)
            }
            for row in bond_result
        ]
        
        # Expiring soon
        warnings = await self.get_expiration_warnings(30)
        
        return {
            "licenses": {
                "by_status": license_stats,
                "total": sum(license_stats.values()),
                "expiring_30_days": warnings["licenses_count"],
            },
            "bonds": {
                "breakdown": bond_stats,
                "expiring_30_days": warnings["bonds_count"],
            },
        }
    
    # ==================== Helpers ====================
    
    def _parse_date(self, value) -> Optional[date]:
        """Parse date from various formats."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
            except:
                pass
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except:
                pass
        return None
