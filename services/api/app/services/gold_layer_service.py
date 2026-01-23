import logging
import uuid
from typing import Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_result import ExtractionResult
from app.models.silver_records import EntityLink
from app.models.gold_records import Shipment, CommercialInvoice, InvoiceLine
from app.models.document_metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class GoldLayerService:
    """
    Service to populate Gold Layer records (Shipments, Invoices) 
    from Bronze extractions and Silver entities.
    """

    @staticmethod
    async def create_gold_records(session: AsyncSession, document_id: str) -> Dict[str, Any]:
        """
        Create or update Gold records for a document.
        """
        logger.info(f"Starting Gold Layer population for document {document_id}")
        
        # 1. Fetch document metadata to know context (if needed)
        # doc = ... 

        # 2. Fetch all extractions for this document
        query = select(ExtractionResult).where(
            ExtractionResult.document_id == uuid.UUID(document_id)
        )
        result = await session.execute(query)
        extractions = result.scalars().all()
        
        if not extractions:
            return {"status": "no_extractions"}

        # 3. Identify record type being built
        # For this phase, we assume we are building a Shipment or Invoice depending on what we find.
        # Simplification: Always create a Shipment for now, and attach an Invoice if invoice fields exist.
        
        # We need a way to group these.
        # Currently 1 Doc -> 1 Shipment (or 1 Invoice)
        
        shipment = await GoldLayerService._get_or_create_shipment(session, extractions)
        invoice = await GoldLayerService._get_or_create_invoice(session, extractions, shipment.id if shipment else None)
        
        # Link document to shipment
        if shipment:
             # shipping logic
             pass

        await session.commit()
        
        return {
            "status": "completed",
            "shipment_id": str(shipment.id) if shipment else None,
            "invoice_id": str(invoice.id) if invoice else None
        }

    @staticmethod
    async def _get_or_create_shipment(session: AsyncSession, extractions: list[ExtractionResult]) -> Optional[Shipment]:
        """
        Derive Shipment record from extractions.
        """
        # Look for key fields
        ref_num = None
        shipper_id = None
        consignee_id = None
        origin = None
        destination = None
        
        for ext in extractions:
            field = ext.field_name.lower()
            val = ext.final_value
            
            if "reference_num" in field or "bol_num" in field or "tracking_num" in field:
                # prioritizing the first one found for now
                if not ref_num: ref_num = str(val)
                
            if "origin" in field: origin = str(val)
            if "destination" in field: destination = str(val)
            
            # Resolve linked entities
            if "shipper" in field:
                shipper_id = await GoldLayerService._get_linked_party_id(session, ext.id)
            if "consignee" in field:
                consignee_id = await GoldLayerService._get_linked_party_id(session, ext.id)

        if not ref_num and not shipper_id and not consignee_id:
            # Not enough info to make a meaningful shipment record
            return None

        # Check if shipment exists by ref_num
        shipment = None
        if ref_num:
            query = select(Shipment).where(Shipment.reference_num == ref_num)
            result = await session.execute(query)
            shipment = result.scalar_one_or_none()
            
        if not shipment:
            shipment = Shipment(
                reference_num=ref_num,
                shipper_id=shipper_id,
                consignee_id=consignee_id,
                origin=origin,
                destination=destination,
                status="draft" 
            )
            session.add(shipment)
            logger.info(f"Created Gold Shipment: {ref_num}")
        else:
            # Update fields if missing
            if not shipment.shipper_id and shipper_id: shipment.shipper_id = shipper_id
            if not shipment.consignee_id and consignee_id: shipment.consignee_id = consignee_id
            
        return shipment

    @staticmethod
    async def _get_or_create_invoice(session: AsyncSession, extractions: list[ExtractionResult], shipment_id: Optional[uuid.UUID]) -> Optional[CommercialInvoice]:
        """
        Derive Commercial Invoice from extractions.
        """
        invoice_num = None
        vendor_id = None
        buyer_id = None
        total_amount = None
        currency = "USD"
        
        for ext in extractions:
            field = ext.field_name.lower()
            val = ext.final_value
            
            if "invoice_num" in field: invoice_num = str(val)
            if "total_amount" in field: 
                try:
                    total_amount = float(str(val).replace("$","").replace(",",""))
                except:
                    pass
            if "currency" in field: currency = str(val)
            
            if "vendor" in field or "seller" in field:
                vendor_id = await GoldLayerService._get_linked_party_id(session, ext.id)
            if "buyer" in field or "bill_to" in field:
                buyer_id = await GoldLayerService._get_linked_party_id(session, ext.id)
                
        if not invoice_num:
            return None

        # Check existence
        query = select(CommercialInvoice).where(CommercialInvoice.invoice_num == invoice_num)
        result = await session.execute(query)
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            invoice = CommercialInvoice(
                invoice_num=invoice_num,
                vendor_id=vendor_id,
                buyer_id=buyer_id,
                total_amount=total_amount,
                currency=currency,
                shipment_id=shipment_id
            )
            session.add(invoice)
            logger.info(f"Created Gold Invoice: {invoice_num}")
            
        return invoice

    @staticmethod
    async def _get_linked_party_id(session: AsyncSession, extraction_id: uuid.UUID) -> Optional[uuid.UUID]:
        """
        Find the Silver Party ID linked to this extraction.
        """
        query = select(EntityLink).where(
            EntityLink.source_entity_id == extraction_id,
            EntityLink.link_type == "extraction_to_party"
        )
        result = await session.execute(query)
        link = result.scalar_one_or_none()
        
        return link.target_entity_id if link else None
