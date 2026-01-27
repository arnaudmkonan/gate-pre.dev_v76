"""
Client Document Preferences Service.

Manages client-specific preferences for document handling:
- Default port of entry
- Preferred entry type
- Auto-apply FTA when applicable
- Client-specific HTS code aliases
- Default payment terms

Task 4.4 from ROADMAP_FULL_WORKFLOW.md
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ClientSettings


class ClientPreferencesService:
    """Service for managing client-specific document preferences."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_preferences(self, client_id: UUID) -> Dict[str, Any]:
        """Get all preferences for a client."""
        # Get client settings
        query = select(ClientSettings).where(ClientSettings.client_id == client_id)
        result = await self.db.execute(query)
        settings = result.scalar_one_or_none()
        
        if not settings:
            # Return defaults
            return self._default_preferences()
        
        # Get custom fields where preferences are stored
        custom = settings.custom_fields or {}
        prefs = custom.get("preferences", {})
        
        return {
            # Standard fields from ClientSettings
            "default_port_of_entry": settings.default_port_of_entry,
            "default_entry_type": settings.default_entry_type,
            "auto_apply_fta": prefs.get("auto_apply_fta", False),
            "default_fta_program": prefs.get("default_fta_program"),
            
            # HTS aliases
            "hts_aliases": prefs.get("hts_aliases", {}),
            
            # Payment terms
            "default_payment_terms": settings.default_payment_terms,
            "billing_email": settings.billing_email,
            "invoice_consolidation": settings.consolidate_invoices,
            
            # Entry defaults
            "auto_calculate_duties": prefs.get("auto_calculate_duties", True),
            "auto_validate_entries": prefs.get("auto_validate_entries", True),
            "default_transport_mode": prefs.get("default_transport_mode"),
            "default_carrier": prefs.get("default_carrier"),
            
            # Document preferences
            "preserve_document_naming": prefs.get("preserve_document_naming", False),
            "auto_link_documents": prefs.get("auto_link_documents", True),
            
            # Notifications
            "notify_on_acceptance": prefs.get("notify_on_acceptance", True),
            "notify_on_rejection": prefs.get("notify_on_rejection", True),
            "notify_on_release": prefs.get("notify_on_release", True),
            "notify_on_hold": prefs.get("notify_on_hold", True),
        }
    
    def _default_preferences(self) -> Dict[str, Any]:
        """Return default preferences."""
        return {
            "default_port_of_entry": None,
            "default_entry_type": "01",
            "auto_apply_fta": False,
            "default_fta_program": None,
            "hts_aliases": {},
            "default_payment_terms": "NET30",
            "billing_email": None,
            "invoice_consolidation": False,
            "auto_calculate_duties": True,
            "auto_validate_entries": True,
            "default_transport_mode": None,
            "default_carrier": None,
            "preserve_document_naming": False,
            "auto_link_documents": True,
            "notify_on_acceptance": True,
            "notify_on_rejection": True,
            "notify_on_release": True,
            "notify_on_hold": True,
        }
    
    async def update_preferences(
        self,
        client_id: UUID,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update client preferences."""
        # Get or create settings
        query = select(ClientSettings).where(ClientSettings.client_id == client_id)
        result = await self.db.execute(query)
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = ClientSettings(client_id=client_id)
            self.db.add(settings)
        
        # Standard ClientSettings fields
        standard_fields = [
            "default_port_of_entry", "default_entry_type",
            "default_payment_terms", "billing_email", "consolidate_invoices"
        ]
        
        for field in standard_fields:
            if field in updates:
                if field == "consolidate_invoices":
                    setattr(settings, field, bool(updates[field]))
                else:
                    setattr(settings, field, updates[field])
        
        # Custom preferences stored in custom_fields
        custom = dict(settings.custom_fields or {})
        prefs = custom.get("preferences", {})
        
        preference_fields = [
            "auto_apply_fta", "default_fta_program", "hts_aliases",
            "auto_calculate_duties", "auto_validate_entries",
            "default_transport_mode", "default_carrier",
            "preserve_document_naming", "auto_link_documents",
            "notify_on_acceptance", "notify_on_rejection",
            "notify_on_release", "notify_on_hold",
        ]
        
        for field in preference_fields:
            if field in updates:
                prefs[field] = updates[field]
        
        custom["preferences"] = prefs
        settings.custom_fields = custom
        
        await self.db.commit()
        
        return await self.get_preferences(client_id)
    
    async def set_default_port(
        self,
        client_id: UUID,
        port_code: str,
    ) -> Dict[str, Any]:
        """Set default port of entry for a client."""
        return await self.update_preferences(client_id, {"default_port_of_entry": port_code})
    
    async def set_default_entry_type(
        self,
        client_id: UUID,
        entry_type: str,
    ) -> Dict[str, Any]:
        """Set default entry type for a client."""
        return await self.update_preferences(client_id, {"default_entry_type": entry_type})
    
    async def set_fta_preferences(
        self,
        client_id: UUID,
        auto_apply: bool,
        default_program: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set FTA preferences for a client."""
        return await self.update_preferences(client_id, {
            "auto_apply_fta": auto_apply,
            "default_fta_program": default_program,
        })
    
    async def add_hts_alias(
        self,
        client_id: UUID,
        client_code: str,
        hts_code: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a client-specific HTS code alias."""
        prefs = await self.get_preferences(client_id)
        aliases = dict(prefs.get("hts_aliases", {}))
        
        aliases[client_code] = {
            "hts_code": hts_code,
            "description": description,
        }
        
        return await self.update_preferences(client_id, {"hts_aliases": aliases})
    
    async def remove_hts_alias(
        self,
        client_id: UUID,
        client_code: str,
    ) -> Dict[str, Any]:
        """Remove a client-specific HTS code alias."""
        prefs = await self.get_preferences(client_id)
        aliases = dict(prefs.get("hts_aliases", {}))
        
        if client_code in aliases:
            del aliases[client_code]
        
        return await self.update_preferences(client_id, {"hts_aliases": aliases})
    
    async def resolve_hts_code(
        self,
        client_id: UUID,
        client_code: str,
    ) -> Optional[str]:
        """Resolve a client's product code to HTS code."""
        prefs = await self.get_preferences(client_id)
        aliases = prefs.get("hts_aliases", {})
        
        if client_code in aliases:
            return aliases[client_code].get("hts_code")
        
        return None
    
    async def apply_defaults_to_entry(
        self,
        client_id: UUID,
        entry_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply client's default preferences to entry data.
        
        Only fills in fields that are empty.
        """
        prefs = await self.get_preferences(client_id)
        
        # Apply defaults where entry doesn't have values
        if not entry_data.get("port_of_entry") and prefs.get("default_port_of_entry"):
            entry_data["port_of_entry"] = prefs["default_port_of_entry"]
        
        if not entry_data.get("entry_type") and prefs.get("default_entry_type"):
            entry_data["entry_type"] = prefs["default_entry_type"]
        
        if not entry_data.get("transport_mode") and prefs.get("default_transport_mode"):
            entry_data["transport_mode"] = prefs["default_transport_mode"]
        
        if not entry_data.get("carrier_code") and prefs.get("default_carrier"):
            entry_data["carrier_code"] = prefs["default_carrier"]
        
        # Mark FTA preference
        entry_data["_auto_apply_fta"] = prefs.get("auto_apply_fta", False)
        entry_data["_default_fta_program"] = prefs.get("default_fta_program")
        
        return entry_data


class EntryDefaultsApplicator:
    """Applies client defaults when creating entries."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.prefs_service = ClientPreferencesService(db)
    
    async def apply_to_entry(
        self,
        entry_data: Dict[str, Any],
        client_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Apply all applicable defaults to entry data."""
        if not client_id:
            return entry_data
        
        # Get client to verify
        query = select(Client).where(Client.id == client_id)
        result = await self.db.execute(query)
        client = result.scalar_one_or_none()
        
        if not client:
            return entry_data
        
        # Apply preferences
        entry_data = await self.prefs_service.apply_defaults_to_entry(client_id, entry_data)
        
        # Apply client info
        if not entry_data.get("importer_of_record_number") and client.ior_number:
            entry_data["importer_of_record_number"] = client.ior_number
        
        if not entry_data.get("importer_of_record_name") and client.name:
            entry_data["importer_of_record_name"] = client.name
        
        return entry_data
