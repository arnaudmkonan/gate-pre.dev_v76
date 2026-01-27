"""
ISF (Importer Security Filing) Service.

Handles ISF/10+2 filing operations:
- Create ISF from shipment or entry data
- Validate 10 data elements
- Generate ABI ISF message
- Track filing status
- Support flexible filing and amendments

Task 3.6 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.isf_filing import ISFFiling, ISFAmendment, ISFStatus


class ISFValidationError:
    """ISF validation error."""
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # error, warning
    
    def to_dict(self):
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }


class ISFService:
    """Service for ISF/10+2 filing operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_isf(
        self,
        shipment_id: Optional[UUID] = None,
        entry_id: Optional[UUID] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> ISFFiling:
        """
        Create a new ISF filing.
        
        Can be created from:
        - Shipment data (auto-populate from shipment)
        - Entry data (auto-populate from entry)
        - Manual data (provide all fields)
        """
        isf = ISFFiling(
            status=ISFStatus.DRAFT.value,
            shipment_id=shipment_id,
            entry_id=entry_id,
            is_flexible=True,
        )
        
        # Auto-populate from shipment if provided
        if shipment_id:
            await self._populate_from_shipment(isf, shipment_id)
        
        # Auto-populate from entry if provided
        if entry_id:
            await self._populate_from_entry(isf, entry_id)
        
        # Override with provided data
        if data:
            self._apply_data(isf, data)
        
        # Generate ISF number
        isf.isf_number = self._generate_isf_number()
        
        self.db.add(isf)
        await self.db.commit()
        await self.db.refresh(isf)
        
        return isf
    
    def _generate_isf_number(self) -> str:
        """Generate unique ISF number."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"ISF-{timestamp}-{str(uuid4())[:4].upper()}"
    
    async def _populate_from_shipment(self, isf: ISFFiling, shipment_id: UUID):
        """Populate ISF from shipment data."""
        from app.models.gold_records import Shipment
        
        query = select(Shipment).where(Shipment.id == shipment_id)
        result = await self.db.execute(query)
        shipment = result.scalar_one_or_none()
        
        if not shipment:
            return
        
        # Map shipment fields to ISF
        isf.importer_of_record_name = shipment.importer_name
        isf.manufacturer_name = shipment.manufacturer_name
        isf.seller_name = shipment.exporter_name
        
        isf.vessel_name = None  # Would need to query transport info
        isf.container_numbers = shipment.container_numbers or []
        isf.master_bill_of_lading = shipment.bol_number
        
        isf.port_of_discharge = shipment.port_of_entry
    
    async def _populate_from_entry(self, isf: ISFFiling, entry_id: UUID):
        """Populate ISF from entry data."""
        from app.models.entry import Entry
        
        query = (
            select(Entry)
            .options(selectinload(Entry.lines))
            .where(Entry.id == entry_id)
        )
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return
        
        # Map entry fields to ISF
        isf.importer_of_record_number = entry.importer_of_record_number
        isf.importer_of_record_name = entry.importer_of_record_name
        isf.consignee_name = entry.ultimate_consignee_name
        isf.consignee_number = entry.ultimate_consignee_number if hasattr(entry, 'ultimate_consignee_number') else None
        
        isf.vessel_name = entry.vessel_name
        isf.voyage_number = entry.voyage_flight_number
        isf.carrier_code = entry.carrier_code
        
        isf.container_numbers = entry.container_numbers or []
        isf.master_bill_of_lading = entry.master_bill
        isf.house_bill_of_lading = entry.house_bill
        
        isf.port_of_discharge = entry.port_of_entry
        isf.port_of_loading = entry.foreign_port_of_lading
        
        # Get HTS codes from lines
        if entry.lines:
            hts_codes = list(set(
                line.hts_code[:6] for line in entry.lines if line.hts_code
            ))
            isf.hts_codes = hts_codes
            if hts_codes:
                isf.hts_primary = hts_codes[0]
            
            # Get countries of origin
            origins = list(set(
                line.country_of_origin for line in entry.lines if line.country_of_origin
            ))
            isf.countries_of_origin = origins
            if origins:
                isf.country_of_origin = origins[0]
            
            # Get manufacturer from first line
            for line in entry.lines:
                if line.manufacturer_name:
                    isf.manufacturer_name = line.manufacturer_name
                    isf.manufacturer_id = line.manufacturer_mid
                    break
    
    def _apply_data(self, isf: ISFFiling, data: Dict[str, Any]):
        """Apply data dictionary to ISF."""
        # Direct field mappings
        direct_fields = [
            'seller_name', 'seller_address', 'seller_city', 'seller_country', 'seller_id',
            'buyer_name', 'buyer_address', 'buyer_city', 'buyer_country', 'buyer_id',
            'importer_of_record_number', 'importer_of_record_name',
            'consignee_number', 'consignee_name', 'consignee_address',
            'manufacturer_name', 'manufacturer_address', 'manufacturer_city', 
            'manufacturer_country', 'manufacturer_id',
            'ship_to_name', 'ship_to_address', 'ship_to_city', 
            'ship_to_state', 'ship_to_postal_code', 'ship_to_country',
            'country_of_origin', 'countries_of_origin',
            'hts_codes', 'hts_primary',
            'stuffing_location_name', 'stuffing_location_address',
            'stuffing_location_city', 'stuffing_location_country',
            'consolidator_name', 'consolidator_address', 
            'consolidator_city', 'consolidator_country', 'consolidator_id',
            'vessel_name', 'voyage_number', 'carrier_code',
            'container_numbers', 'master_bill_of_lading', 'house_bill_of_lading',
            'port_of_loading', 'port_of_discharge',
            'estimated_departure', 'estimated_arrival',
            'filer_code', 'bond_type', 'notes',
        ]
        
        for field in direct_fields:
            if field in data:
                setattr(isf, field, data[field])
    
    async def get_isf(self, isf_id: UUID) -> Optional[ISFFiling]:
        """Get ISF by ID."""
        query = select(ISFFiling).where(ISFFiling.id == isf_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_isf_by_shipment(self, shipment_id: UUID) -> Optional[ISFFiling]:
        """Get ISF for a shipment."""
        query = select(ISFFiling).where(ISFFiling.shipment_id == shipment_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_isf_by_entry(self, entry_id: UUID) -> Optional[ISFFiling]:
        """Get ISF for an entry."""
        query = select(ISFFiling).where(ISFFiling.entry_id == entry_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def update_isf(
        self,
        isf_id: UUID,
        data: Dict[str, Any],
    ) -> ISFFiling:
        """Update ISF with new data."""
        isf = await self.get_isf(isf_id)
        if not isf:
            raise ValueError(f"ISF {isf_id} not found")
        
        self._apply_data(isf, data)
        
        await self.db.commit()
        await self.db.refresh(isf)
        
        return isf
    
    async def validate_isf(self, isf_id: UUID) -> Dict[str, Any]:
        """
        Validate ISF for filing.
        
        Checks all 10 required elements and transport info.
        """
        isf = await self.get_isf(isf_id)
        if not isf:
            return {"error": "ISF not found"}
        
        errors = []
        warnings = []
        
        # 1. Seller
        if not isf.seller_name:
            errors.append(ISFValidationError("seller_name", "Seller name is required"))
        elif not isf.seller_address and not isf.seller_country:
            warnings.append(ISFValidationError("seller_address", "Seller address recommended", "warning"))
        
        # 2. Buyer
        if not isf.buyer_name:
            errors.append(ISFValidationError("buyer_name", "Buyer name is required"))
        
        # 3. Importer of Record
        if not isf.importer_of_record_number:
            errors.append(ISFValidationError("importer_of_record_number", "Importer of record number is required"))
        
        # 4. Consignee
        if not isf.consignee_number and not isf.consignee_name:
            errors.append(ISFValidationError("consignee", "Consignee number or name is required"))
        
        # 5. Manufacturer
        if not isf.manufacturer_name:
            errors.append(ISFValidationError("manufacturer_name", "Manufacturer name is required"))
        
        # 6. Ship To
        if not isf.ship_to_name and not isf.ship_to_address:
            errors.append(ISFValidationError("ship_to", "Ship to party is required"))
        
        # 7. Country of Origin
        if not isf.country_of_origin and not isf.countries_of_origin:
            errors.append(ISFValidationError("country_of_origin", "Country of origin is required"))
        
        # 8. HTS Codes
        if not isf.hts_codes and not isf.hts_primary:
            errors.append(ISFValidationError("hts_codes", "At least one HTS code (6-digit) is required"))
        else:
            # Validate HTS format
            for hts in (isf.hts_codes or []):
                if len(hts.replace(".", "")) < 6:
                    warnings.append(ISFValidationError(
                        "hts_codes", 
                        f"HTS code {hts} should be at least 6 digits",
                        "warning"
                    ))
        
        # 9. Stuffing Location
        if not isf.stuffing_location_name:
            if isf.is_flexible:
                warnings.append(ISFValidationError(
                    "stuffing_location", 
                    "Stuffing location required before cargo release",
                    "warning"
                ))
            else:
                errors.append(ISFValidationError("stuffing_location", "Stuffing location is required"))
        
        # 10. Consolidator
        if not isf.consolidator_name:
            if isf.is_flexible:
                warnings.append(ISFValidationError(
                    "consolidator", 
                    "Consolidator required before cargo release",
                    "warning"
                ))
            else:
                errors.append(ISFValidationError("consolidator", "Consolidator is required"))
        
        # Transport Info
        if not isf.vessel_name:
            warnings.append(ISFValidationError("vessel_name", "Vessel name recommended", "warning"))
        
        if not isf.master_bill_of_lading:
            warnings.append(ISFValidationError("master_bill_of_lading", "Master B/L recommended", "warning"))
        
        # Timing check
        if isf.estimated_departure:
            hours_until_departure = (isf.estimated_departure - datetime.now(timezone.utc)).total_seconds() / 3600
            if hours_until_departure < 24:
                errors.append(ISFValidationError(
                    "timing",
                    f"ISF must be filed 24 hours before departure. Only {hours_until_departure:.1f} hours remaining."
                ))
        
        # Update ISF validation status
        isf.validation_errors = [e.to_dict() for e in errors]
        isf.is_valid = len(errors) == 0
        await self.db.commit()
        
        return {
            "isf_id": str(isf_id),
            "is_valid": isf.is_valid,
            "is_flexible": isf.is_flexible,
            "completeness": isf.get_completeness_percentage(),
            "missing_elements": isf.get_missing_elements(),
            "errors": [e.to_dict() for e in errors],
            "warnings": [w.to_dict() for w in warnings],
            "can_file": isf.is_valid or isf.is_flexible,
        }
    
    async def file_isf(self, isf_id: UUID) -> Dict[str, Any]:
        """
        Submit ISF to CBP.
        
        In production, would transmit via ABI.
        """
        isf = await self.get_isf(isf_id)
        if not isf:
            return {"error": "ISF not found"}
        
        # Validate first
        validation = await self.validate_isf(isf_id)
        if not validation.get("can_file"):
            return {
                "error": "ISF cannot be filed",
                "validation": validation,
            }
        
        # Generate transaction number
        isf.transaction_number = f"ISF{datetime.now().strftime('%Y%m%d%H%M%S')}"
        isf.status = ISFStatus.SUBMITTED.value
        isf.filed_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(isf)
        
        return {
            "isf_id": str(isf_id),
            "isf_number": isf.isf_number,
            "transaction_number": isf.transaction_number,
            "status": isf.status,
            "filed_at": isf.filed_at.isoformat(),
            "message": "ISF submitted to CBP",
            "is_flexible": isf.is_flexible,
            "next_steps": [
                "Monitor for CBP acceptance/rejection",
                "Complete missing elements if flexible filing" if isf.is_flexible else None,
                "Match to entry when filed",
            ],
        }
    
    async def match_isf_to_entry(
        self,
        isf_id: UUID,
        entry_id: UUID,
    ) -> Dict[str, Any]:
        """Link ISF to an entry."""
        isf = await self.get_isf(isf_id)
        if not isf:
            return {"error": "ISF not found"}
        
        isf.entry_id = entry_id
        isf.status = ISFStatus.MATCHED.value
        
        await self.db.commit()
        
        return {
            "isf_id": str(isf_id),
            "entry_id": str(entry_id),
            "status": isf.status,
            "message": "ISF matched to entry",
        }
    
    async def amend_isf(
        self,
        isf_id: UUID,
        changes: Dict[str, Any],
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        File an ISF amendment.
        
        Tracks what changed and files update with CBP.
        """
        isf = await self.get_isf(isf_id)
        if not isf:
            return {"error": "ISF not found"}
        
        # Track old values
        changed_fields = {}
        for field, new_value in changes.items():
            old_value = getattr(isf, field, None)
            if old_value != new_value:
                changed_fields[field] = {
                    "old": old_value if not isinstance(old_value, (list, dict)) else None,
                    "new": new_value if not isinstance(new_value, (list, dict)) else None,
                }
        
        if not changed_fields:
            return {
                "error": "No changes detected",
                "isf_id": str(isf_id),
            }
        
        # Apply changes
        self._apply_data(isf, changes)
        
        # Increment amendment count
        isf.amendment_count = (isf.amendment_count or 0) + 1
        isf.status = ISFStatus.AMENDED.value
        
        # Create amendment record
        amendment = ISFAmendment(
            isf_id=isf_id,
            amendment_number=isf.amendment_count,
            changed_fields=changed_fields,
            reason=reason,
            filed_at=datetime.now(timezone.utc),
            status="pending",
            filed_by="user",
        )
        self.db.add(amendment)
        
        await self.db.commit()
        await self.db.refresh(isf)
        
        return {
            "isf_id": str(isf_id),
            "amendment_number": isf.amendment_count,
            "changed_fields": changed_fields,
            "status": isf.status,
            "message": f"ISF amendment #{isf.amendment_count} filed",
        }
    
    async def generate_isf_abi_message(self, isf_id: UUID) -> Dict[str, Any]:
        """
        Generate ABI message for ISF filing.
        
        Creates ISF-10 message format for CBP submission.
        """
        isf = await self.get_isf(isf_id)
        if not isf:
            return {"error": "ISF not found"}
        
        # Build ISF message
        message = {
            "message_type": "IS",  # ISF
            "transaction_type": "ISF-10",
            "isf_number": isf.isf_number,
            "flexible_filing": isf.is_flexible,
            
            "10_elements": {
                "1_seller": {
                    "name": isf.seller_name,
                    "address": isf.seller_address,
                    "city": isf.seller_city,
                    "country": isf.seller_country,
                },
                "2_buyer": {
                    "name": isf.buyer_name,
                    "address": isf.buyer_address,
                    "country": isf.buyer_country,
                },
                "3_importer_of_record": {
                    "number": isf.importer_of_record_number,
                    "name": isf.importer_of_record_name,
                },
                "4_consignee": {
                    "number": isf.consignee_number,
                    "name": isf.consignee_name,
                },
                "5_manufacturer": {
                    "name": isf.manufacturer_name,
                    "mid": isf.manufacturer_id,
                    "country": isf.manufacturer_country,
                },
                "6_ship_to": {
                    "name": isf.ship_to_name,
                    "address": isf.ship_to_address,
                    "city": isf.ship_to_city,
                    "country": isf.ship_to_country,
                },
                "7_country_of_origin": isf.countries_of_origin or [isf.country_of_origin],
                "8_hts_codes": isf.hts_codes or [isf.hts_primary] if isf.hts_primary else [],
                "9_stuffing_location": {
                    "name": isf.stuffing_location_name,
                    "address": isf.stuffing_location_address,
                    "country": isf.stuffing_location_country,
                },
                "10_consolidator": {
                    "name": isf.consolidator_name,
                    "address": isf.consolidator_address,
                    "country": isf.consolidator_country,
                },
            },
            
            "transport": {
                "vessel": isf.vessel_name,
                "voyage": isf.voyage_number,
                "carrier_code": isf.carrier_code,
                "port_of_loading": isf.port_of_loading,
                "port_of_discharge": isf.port_of_discharge,
                "bill_of_lading": isf.master_bill_of_lading,
                "containers": isf.container_numbers or [],
            },
            
            "dates": {
                "estimated_departure": isf.estimated_departure.isoformat() if isf.estimated_departure else None,
                "estimated_arrival": isf.estimated_arrival.isoformat() if isf.estimated_arrival else None,
            },
        }
        
        return {
            "isf_id": str(isf_id),
            "message_type": "ISF-10",
            "message": message,
            "abi_ready": isf.is_valid,
        }
    
    async def list_isf_filings(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List ISF filings with optional filtering."""
        query = select(ISFFiling).order_by(ISFFiling.created_at.desc())
        
        if status:
            query = query.where(ISFFiling.status == status)
        
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        filings = result.scalars().all()
        
        return {
            "count": len(filings),
            "filings": [f.to_dict() for f in filings],
        }
    
    async def get_pending_isf_count(self) -> Dict[str, Any]:
        """Get count of ISF filings by status."""
        from sqlalchemy import func
        
        query = (
            select(
                ISFFiling.status,
                func.count(ISFFiling.id).label("count")
            )
            .group_by(ISFFiling.status)
        )
        
        result = await self.db.execute(query)
        counts = {row.status: row.count for row in result}
        
        return {
            "total": sum(counts.values()),
            "by_status": counts,
        }
