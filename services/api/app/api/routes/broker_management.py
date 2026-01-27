"""
Broker License, Permit & Bond Management API Routes.

CRUD operations for broker licenses, port permits, and bonds.

Task 3.7 from ROADMAP_FULL_WORKFLOW.md
"""
from typing import Optional, List
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


router = APIRouter(prefix="/api/broker", tags=["Broker Management"])


# ==================== Request/Response Models ====================

class LicenseCreate(BaseModel):
    """Create broker license request."""
    license_number: str
    broker_name: str
    filer_code: Optional[str] = None
    broker_type: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    issuing_district: Optional[str] = None
    permitted_ports: Optional[List[str]] = None
    primary_contact: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class LicenseUpdate(BaseModel):
    """Update broker license request."""
    broker_name: Optional[str] = None
    filer_code: Optional[str] = None
    status: Optional[str] = None
    expiration_date: Optional[str] = None
    permitted_ports: Optional[List[str]] = None
    primary_contact: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None


class PortPermitCreate(BaseModel):
    """Add port permit request."""
    port_code: str
    port_name: Optional[str] = None
    district_code: Optional[str] = None


class BondCreate(BaseModel):
    """Create bond request."""
    bond_number: str
    bond_type: str = "continuous"
    activity_code: Optional[str] = "1"
    surety_code: Optional[str] = None
    surety_name: Optional[str] = None
    bond_amount: float
    principal_name: Optional[str] = None
    principal_ior_number: Optional[str] = None
    effective_date: Optional[str] = None
    expiration_date: Optional[str] = None
    license_id: Optional[str] = None
    client_id: Optional[str] = None
    covered_ports: Optional[List[str]] = None
    notes: Optional[str] = None


class BondUpdate(BaseModel):
    """Update bond request."""
    status: Optional[str] = None
    surety_code: Optional[str] = None
    bond_amount: Optional[float] = None
    expiration_date: Optional[str] = None
    notes: Optional[str] = None


# ==================== License Endpoints ====================

@router.post("/licenses")
async def create_license(
    request: LicenseCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new broker license."""
    from app.services.broker_management_service import BrokerManagementService
    
    service = BrokerManagementService(db)
    
    # Check for duplicate
    existing = await service.get_license_by_number(request.license_number)
    if existing:
        raise HTTPException(status_code=400, detail="License number already exists")
    
    try:
        license = await service.create_license(request.model_dump())
        return {
            "license": license.to_dict(),
            "message": "License created successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/licenses")
async def list_licenses(
    status: Optional[str] = Query(None, description="Filter by status"),
    expiring_days: Optional[int] = Query(None, description="Show licenses expiring within N days"),
    db: AsyncSession = Depends(get_db),
):
    """List all broker licenses."""
    from app.services.broker_management_service import BrokerManagementService
    
    service = BrokerManagementService(db)
    licenses = await service.list_licenses(
        status=status,
        expiring_within_days=expiring_days,
    )
    
    return {
        "count": len(licenses),
        "licenses": [l.to_dict() for l in licenses],
    }


@router.get("/licenses/{license_id}")
async def get_license(
    license_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get license details."""
    from app.services.broker_management_service import BrokerManagementService
    
    try:
        license_uuid = UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid license ID")
    
    service = BrokerManagementService(db)
    license = await service.get_license(license_uuid)
    
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    # Get permits
    permits = await service.get_permits_for_license(license_uuid)
    
    result = license.to_dict()
    result["permits"] = [p.to_dict() for p in permits]
    
    return result


@router.put("/licenses/{license_id}")
async def update_license(
    license_id: str,
    request: LicenseUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a broker license."""
    from app.services.broker_management_service import BrokerManagementService
    
    try:
        license_uuid = UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid license ID")
    
    service = BrokerManagementService(db)
    
    try:
        license = await service.update_license(
            license_uuid,
            request.model_dump(exclude_none=True),
        )
        return {
            "license": license.to_dict(),
            "message": "License updated successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/licenses/{license_id}/renew")
async def renew_license(
    license_id: str,
    new_expiration: str = Query(..., description="New expiration date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """Renew a broker license."""
    from app.services.broker_management_service import BrokerManagementService
    from datetime import datetime
    
    try:
        license_uuid = UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid license ID")
    
    try:
        exp_date = datetime.strptime(new_expiration, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    service = BrokerManagementService(db)
    
    try:
        license = await service.renew_license(license_uuid, exp_date)
        return {
            "license": license.to_dict(),
            "message": "License renewed successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Port Permit Endpoints ====================

@router.post("/licenses/{license_id}/permits")
async def add_port_permit(
    license_id: str,
    request: PortPermitCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a port permit to a license."""
    from app.services.broker_management_service import BrokerManagementService
    
    try:
        license_uuid = UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid license ID")
    
    service = BrokerManagementService(db)
    
    # Verify license exists
    license = await service.get_license(license_uuid)
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    permit = await service.add_port_permit(
        license_uuid,
        request.port_code,
        request.port_name,
        request.district_code,
    )
    
    return {
        "permit": permit.to_dict(),
        "message": "Port permit added successfully",
    }


@router.get("/licenses/{license_id}/permits")
async def list_port_permits(
    license_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all port permits for a license."""
    from app.services.broker_management_service import BrokerManagementService
    
    try:
        license_uuid = UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid license ID")
    
    service = BrokerManagementService(db)
    permits = await service.get_permits_for_license(license_uuid)
    
    return {
        "count": len(permits),
        "permits": [p.to_dict() for p in permits],
    }


@router.get("/licenses/{license_id}/check-port/{port_code}")
async def check_port_permit(
    license_id: str,
    port_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Check if license has permit for a specific port."""
    from app.services.broker_management_service import BrokerManagementService
    
    try:
        license_uuid = UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid license ID")
    
    service = BrokerManagementService(db)
    has_permit = await service.check_port_permit(license_uuid, port_code)
    
    return {
        "port_code": port_code,
        "has_permit": has_permit,
    }


# ==================== Bond Endpoints ====================

@router.post("/bonds")
async def create_bond(
    request: BondCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new bond."""
    from app.services.broker_management_service import BrokerManagementService
    
    service = BrokerManagementService(db)
    
    # Check for duplicate
    existing = await service.get_bond_by_number(request.bond_number)
    if existing:
        raise HTTPException(status_code=400, detail="Bond number already exists")
    
    try:
        bond = await service.create_bond(request.model_dump())
        return {
            "bond": bond.to_dict(),
            "message": "Bond created successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bonds")
async def list_bonds(
    bond_type: Optional[str] = Query(None, description="Filter by type (continuous, single_transaction)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    client_id: Optional[str] = Query(None, description="Filter by client"),
    expiring_days: Optional[int] = Query(None, description="Show bonds expiring within N days"),
    db: AsyncSession = Depends(get_db),
):
    """List all bonds."""
    from app.services.broker_management_service import BrokerManagementService
    
    service = BrokerManagementService(db)
    
    client_uuid = UUID(client_id) if client_id else None
    
    bonds = await service.list_bonds(
        bond_type=bond_type,
        status=status,
        client_id=client_uuid,
        expiring_within_days=expiring_days,
    )
    
    return {
        "count": len(bonds),
        "bonds": [b.to_dict() for b in bonds],
    }


@router.get("/bonds/{bond_id}")
async def get_bond(
    bond_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get bond details."""
    from app.services.broker_management_service import BrokerManagementService
    
    try:
        bond_uuid = UUID(bond_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bond ID")
    
    service = BrokerManagementService(db)
    bond = await service.get_bond(bond_uuid)
    
    if not bond:
        raise HTTPException(status_code=404, detail="Bond not found")
    
    return bond.to_dict()


@router.put("/bonds/{bond_id}")
async def update_bond(
    bond_id: str,
    request: BondUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a bond."""
    from app.services.broker_management_service import BrokerManagementService
    
    try:
        bond_uuid = UUID(bond_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bond ID")
    
    service = BrokerManagementService(db)
    
    try:
        bond = await service.update_bond(
            bond_uuid,
            request.model_dump(exclude_none=True),
        )
        return {
            "bond": bond.to_dict(),
            "message": "Bond updated successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bonds/{bond_id}/use")
async def use_bond(
    bond_id: str,
    amount: float = Query(..., description="Amount to use from bond"),
    entry_number: Optional[str] = Query(None, description="Entry number for STB"),
    db: AsyncSession = Depends(get_db),
):
    """Record usage of a bond (for STB tracking)."""
    from app.services.broker_management_service import BrokerManagementService
    from decimal import Decimal
    
    try:
        bond_uuid = UUID(bond_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bond ID")
    
    service = BrokerManagementService(db)
    
    try:
        bond = await service.use_bond(bond_uuid, Decimal(str(amount)), entry_number)
        return {
            "bond": bond.to_dict(),
            "message": f"Recorded ${amount:.2f} usage on bond",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bonds/{bond_id}/sufficiency")
async def check_bond_sufficiency(
    bond_id: str,
    annual_duty_estimate: Optional[float] = Query(None, description="Estimated annual duties"),
    db: AsyncSession = Depends(get_db),
):
    """Check if bond has sufficient coverage."""
    from app.services.broker_management_service import BrokerManagementService
    
    try:
        bond_uuid = UUID(bond_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid bond ID")
    
    service = BrokerManagementService(db)
    result = await service.check_bond_sufficiency(bond_uuid, annual_duty_estimate)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


# ==================== Validation & Warnings ====================

@router.get("/warnings")
async def get_expiration_warnings(
    days: int = Query(30, description="Days to look ahead"),
    db: AsyncSession = Depends(get_db),
):
    """Get all items expiring within given days."""
    from app.services.broker_management_service import BrokerManagementService
    
    service = BrokerManagementService(db)
    return await service.get_expiration_warnings(days)


@router.post("/validate-entry")
async def validate_for_entry(
    entry_value: float = Query(..., description="Entry value"),
    client_id: Optional[str] = Query(None),
    port_code: Optional[str] = Query(None),
    license_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Validate broker can file an entry.
    
    Checks license status, port permits, and bond sufficiency.
    """
    from app.services.broker_management_service import BrokerManagementService
    
    service = BrokerManagementService(db)
    
    result = await service.validate_for_entry(
        entry_value=entry_value,
        client_id=UUID(client_id) if client_id else None,
        port_code=port_code,
        license_id=UUID(license_id) if license_id else None,
    )
    
    return result


@router.get("/stats")
async def get_broker_statistics(
    db: AsyncSession = Depends(get_db),
):
    """Get broker management statistics."""
    from app.services.broker_management_service import BrokerManagementService
    
    service = BrokerManagementService(db)
    return await service.get_statistics()


# ==================== Reference Data ====================

@router.get("/reference/surety-codes")
async def get_surety_codes():
    """Get list of surety company codes."""
    from app.models.broker_management import SURETY_CODES
    
    return {
        "surety_codes": [
            {"code": code, "name": name}
            for code, name in SURETY_CODES.items()
        ]
    }


@router.get("/reference/activity-codes")
async def get_activity_codes():
    """Get list of bond activity codes."""
    from app.models.broker_management import BOND_ACTIVITY_CODES
    
    return {
        "activity_codes": [
            {"code": code, "description": desc}
            for code, desc in BOND_ACTIVITY_CODES.items()
        ]
    }
