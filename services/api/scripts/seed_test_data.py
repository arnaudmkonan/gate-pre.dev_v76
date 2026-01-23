"""
Seed script for testing Data Fabric features.

Run with:
    docker compose exec api python -m scripts.seed_test_data
"""

import asyncio
import uuid
from datetime import datetime, timedelta
import random

async def seed_data():
    """Seed test data for Data Fabric demonstration."""
    from app.core.database import async_session
    from app.models.silver_records import Party, Product, Address
    from app.models.gold_records import Shipment, CommercialInvoice, InvoiceLine
    
    async with async_session() as session:
        print("🌱 Seeding test data...")
        
        # --- Parties (with intentional duplicates for Golden Records testing) ---
        parties_data = [
            # Real distinct parties
            {"canonical_name": "Acme Corporation", "party_type": "vendor", "tax_id": "12-3456789", "aliases": ["Acme Corp", "ACME"]},
            {"canonical_name": "Global Logistics Inc", "party_type": "carrier", "tax_id": "98-7654321", "aliases": ["Global Logistics"]},
            {"canonical_name": "Pacific Trading Co", "party_type": "importer", "tax_id": "45-6789012", "aliases": ["Pacific Trading"]},
            {"canonical_name": "Shanghai Manufacturing Ltd", "party_type": "manufacturer", "tax_id": None, "aliases": ["Shanghai Mfg"]},
            {"canonical_name": "Harbor Freight Services", "party_type": "freight_forwarder", "tax_id": "78-9012345", "aliases": ["Harbor Freight"]},
            
            # Duplicates for testing (variations of existing parties)
            {"canonical_name": "ACME Corporation", "party_type": "vendor", "tax_id": None, "aliases": ["Acme"]},  # Duplicate of Acme
            {"canonical_name": "Acme Corp.", "party_type": "supplier", "tax_id": None, "aliases": []},  # Another duplicate
            {"canonical_name": "Global Logistics", "party_type": "carrier", "tax_id": None, "aliases": ["GL Inc"]},  # Duplicate of Global Logistics Inc
            {"canonical_name": "Pacific Trading Company", "party_type": "importer", "tax_id": None, "aliases": ["PTC"]},  # Duplicate
            
            # More distinct parties
            {"canonical_name": "US Customs Broker LLC", "party_type": "customs_broker", "tax_id": "11-2233445", "aliases": ["USCB"]},
            {"canonical_name": "East Coast Imports", "party_type": "importer", "tax_id": "22-3344556", "aliases": ["ECI", "East Coast"]},
            {"canonical_name": "West Coast Exports", "party_type": "exporter", "tax_id": "33-4455667", "aliases": ["WCE"]},
            {"canonical_name": "Continental Shipping", "party_type": "carrier", "tax_id": "44-5566778", "aliases": ["CS"]},
            {"canonical_name": "Transocean Freight", "party_type": "carrier", "tax_id": "55-6677889", "aliases": ["TOF", "Transocean"]},
        ]
        
        created_parties = []
        for p_data in parties_data:
            party = Party(**p_data)
            session.add(party)
            created_parties.append(party)
        
        await session.flush()
        print(f"  ✓ Created {len(created_parties)} parties")
        
        # Add addresses to some parties
        addresses_data = [
            {"party_id": created_parties[0].id, "street": "123 Industrial Blvd", "city": "Los Angeles", "state": "CA", "postal_code": "90001", "country": "USA"},
            {"party_id": created_parties[1].id, "street": "456 Port Road", "city": "Long Beach", "state": "CA", "postal_code": "90802", "country": "USA"},
            {"party_id": created_parties[2].id, "street": "789 Trade Center", "city": "San Francisco", "state": "CA", "postal_code": "94102", "country": "USA"},
            {"party_id": created_parties[3].id, "street": "100 Manufacturing Zone", "city": "Shanghai", "state": None, "postal_code": "200000", "country": "China"},
        ]
        
        for a_data in addresses_data:
            address = Address(**a_data)
            session.add(address)
        
        print(f"  ✓ Created {len(addresses_data)} addresses")
        
        # --- Products (with intentional duplicates) ---
        products_data = [
            # Distinct products
            {"description": "Industrial Steel Bearings, 50mm", "hs_code": "8482.10.50", "country_of_origin": "China", "unit_of_measure": "PCS", "aliases": ["Steel Bearings 50mm"]},
            {"description": "Automotive Brake Pads, Set of 4", "hs_code": "8708.30.50", "country_of_origin": "Germany", "unit_of_measure": "SET", "aliases": ["Brake Pads"]},
            {"description": "Electronic Circuit Boards PCB", "hs_code": "8534.00.00", "country_of_origin": "Taiwan", "unit_of_measure": "PCS", "aliases": ["PCB", "Circuit Boards"]},
            {"description": "Cotton T-Shirts, Assorted", "hs_code": "6109.10.00", "country_of_origin": "Vietnam", "unit_of_measure": "DOZ", "aliases": ["T-Shirts"]},
            {"description": "Stainless Steel Fasteners", "hs_code": "7318.15.00", "country_of_origin": "India", "unit_of_measure": "KG", "aliases": ["Fasteners", "SS Fasteners"]},
            
            # Duplicates for testing
            {"description": "Steel Bearings 50mm Industrial", "hs_code": "8482.10.50", "country_of_origin": "China", "unit_of_measure": "PCS", "aliases": []},  # Duplicate
            {"description": "Brake Pads Automotive (Set)", "hs_code": "8708.30.50", "country_of_origin": "Germany", "unit_of_measure": "SET", "aliases": []},  # Duplicate
            {"description": "PCB Electronic Circuit Boards", "hs_code": "8534.00.00", "country_of_origin": "Taiwan", "unit_of_measure": "PCS", "aliases": []},  # Duplicate
            
            # More distinct products
            {"description": "LED Light Bulbs 60W Equivalent", "hs_code": "8539.50.00", "country_of_origin": "China", "unit_of_measure": "PCS", "aliases": ["LED Bulbs"]},
            {"description": "Rubber Gaskets Industrial", "hs_code": "4016.93.00", "country_of_origin": "Malaysia", "unit_of_measure": "PCS", "aliases": ["Gaskets"]},
            {"description": "Aluminum Extrusions 6061-T6", "hs_code": "7604.29.10", "country_of_origin": "USA", "unit_of_measure": "KG", "aliases": ["Aluminum Profiles"]},
        ]
        
        created_products = []
        for pr_data in products_data:
            product = Product(**pr_data)
            session.add(product)
            created_products.append(product)
        
        await session.flush()
        print(f"  ✓ Created {len(created_products)} products")
        
        # --- Shipments ---
        shipments_data = [
            {
                "reference_num": "SHP-2026-001",
                "origin": "Shanghai, China",
                "destination": "Los Angeles, CA",
                "ship_date": datetime.now() - timedelta(days=15),
                "status": "in_transit",
                "shipper_id": created_parties[3].id,  # Shanghai Manufacturing
                "consignee_id": created_parties[0].id,  # Acme Corporation
            },
            {
                "reference_num": "SHP-2026-002",
                "origin": "Hamburg, Germany",
                "destination": "New York, NY",
                "ship_date": datetime.now() - timedelta(days=10),
                "status": "delivered",
                "shipper_id": created_parties[11].id,  # West Coast Exports
                "consignee_id": created_parties[10].id,  # East Coast Imports
            },
            {
                "reference_num": "SHP-2026-003",
                "origin": "Taipei, Taiwan",
                "destination": "San Francisco, CA",
                "ship_date": datetime.now() - timedelta(days=5),
                "status": "customs_hold",
                "shipper_id": created_parties[3].id,
                "consignee_id": created_parties[2].id,  # Pacific Trading
            },
            {
                "reference_num": "SHP-2026-004",
                "origin": "Mumbai, India",
                "destination": "Long Beach, CA",
                "ship_date": datetime.now() - timedelta(days=20),
                "status": "delivered",
                "shipper_id": None,
                "consignee_id": created_parties[0].id,
            },
            {
                "reference_num": "SHP-2026-005",
                "origin": "Ho Chi Minh City, Vietnam",
                "destination": "Seattle, WA",
                "ship_date": datetime.now() - timedelta(days=8),
                "status": "in_transit",
                "shipper_id": None,
                "consignee_id": created_parties[10].id,
            },
        ]
        
        created_shipments = []
        for s_data in shipments_data:
            shipment = Shipment(**s_data)
            session.add(shipment)
            created_shipments.append(shipment)
        
        await session.flush()
        print(f"  ✓ Created {len(created_shipments)} shipments")
        
        # --- Commercial Invoices ---
        invoices_data = [
            {
                "invoice_num": "INV-2026-0001",
                "invoice_date": datetime.now() - timedelta(days=16),
                "currency": "USD",
                "total_amount": 45000.00,
                "vendor_id": created_parties[3].id,
                "buyer_id": created_parties[0].id,
                "shipment_id": created_shipments[0].id,
            },
            {
                "invoice_num": "INV-2026-0002",
                "invoice_date": datetime.now() - timedelta(days=11),
                "currency": "EUR",
                "total_amount": 28500.00,
                "vendor_id": created_parties[11].id,
                "buyer_id": created_parties[10].id,
                "shipment_id": created_shipments[1].id,
            },
            {
                "invoice_num": "INV-2026-0003",
                "invoice_date": datetime.now() - timedelta(days=6),
                "currency": "USD",
                "total_amount": 72000.00,
                "vendor_id": created_parties[3].id,
                "buyer_id": created_parties[2].id,
                "shipment_id": created_shipments[2].id,
            },
            {
                "invoice_num": "INV-2026-0004",
                "invoice_date": datetime.now() - timedelta(days=21),
                "currency": "USD",
                "total_amount": 15750.50,
                "vendor_id": None,
                "buyer_id": created_parties[0].id,
                "shipment_id": created_shipments[3].id,
            },
            {
                "invoice_num": "INV-2026-0005",
                "invoice_date": datetime.now() - timedelta(days=9),
                "currency": "USD",
                "total_amount": 33200.00,
                "vendor_id": None,
                "buyer_id": created_parties[10].id,
                "shipment_id": created_shipments[4].id,
            },
        ]
        
        created_invoices = []
        for inv_data in invoices_data:
            invoice = CommercialInvoice(**inv_data)
            session.add(invoice)
            created_invoices.append(invoice)
        
        await session.flush()
        print(f"  ✓ Created {len(created_invoices)} invoices")
        
        # --- Invoice Lines ---
        lines_data = [
            # Invoice 1 lines
            {"invoice_id": created_invoices[0].id, "line_num": 1, "description": "Industrial Steel Bearings, 50mm", "quantity": 500, "unit_price": 45.00, "amount": 22500.00, "hs_code": "8482.10.50", "product_id": created_products[0].id},
            {"invoice_id": created_invoices[0].id, "line_num": 2, "description": "Electronic Circuit Boards PCB", "quantity": 150, "unit_price": 150.00, "amount": 22500.00, "hs_code": "8534.00.00", "product_id": created_products[2].id},
            
            # Invoice 2 lines
            {"invoice_id": created_invoices[1].id, "line_num": 1, "description": "Automotive Brake Pads, Set of 4", "quantity": 200, "unit_price": 142.50, "amount": 28500.00, "hs_code": "8708.30.50", "product_id": created_products[1].id},
            
            # Invoice 3 lines
            {"invoice_id": created_invoices[2].id, "line_num": 1, "description": "PCB Electronic Circuit Boards", "quantity": 300, "unit_price": 180.00, "amount": 54000.00, "hs_code": "8534.00.00", "product_id": created_products[7].id},
            {"invoice_id": created_invoices[2].id, "line_num": 2, "description": "LED Light Bulbs 60W Equivalent", "quantity": 2000, "unit_price": 9.00, "amount": 18000.00, "hs_code": "8539.50.00", "product_id": created_products[8].id},
            
            # Invoice 4 lines
            {"invoice_id": created_invoices[3].id, "line_num": 1, "description": "Stainless Steel Fasteners", "quantity": 750, "unit_price": 21.00, "amount": 15750.00, "hs_code": "7318.15.00", "product_id": created_products[4].id},
            
            # Invoice 5 lines
            {"invoice_id": created_invoices[4].id, "line_num": 1, "description": "Cotton T-Shirts, Assorted", "quantity": 1200, "unit_price": 18.00, "amount": 21600.00, "hs_code": "6109.10.00", "product_id": created_products[3].id},
            {"invoice_id": created_invoices[4].id, "line_num": 2, "description": "Rubber Gaskets Industrial", "quantity": 800, "unit_price": 14.50, "amount": 11600.00, "hs_code": "4016.93.00", "product_id": created_products[9].id},
        ]
        
        for line_data in lines_data:
            line = InvoiceLine(**line_data)
            session.add(line)
        
        print(f"  ✓ Created {len(lines_data)} invoice lines")
        
        await session.commit()
        
        print("\n✅ Seed data complete!")
        print(f"   Parties: {len(created_parties)} (with ~4 duplicates)")
        print(f"   Products: {len(created_products)} (with ~3 duplicates)")
        print(f"   Shipments: {len(created_shipments)}")
        print(f"   Invoices: {len(created_invoices)}")
        print(f"   Invoice Lines: {len(lines_data)}")
        print("\n🔍 Test the Duplicates tab to see Golden Record merge candidates!")


if __name__ == "__main__":
    asyncio.run(seed_data())
