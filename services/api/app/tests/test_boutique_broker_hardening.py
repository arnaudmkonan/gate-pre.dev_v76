"""Regression tests for Boutique Broker MVP copy-sale hardening."""

import asyncio
import hashlib
import secrets
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.models.client_portal import ClientUser, ClientUserRole
from app.models.extraction_result import ExtractionResult
from app.services.audit_service import AUDIT_LOG_RETENTION_DAYS
from app.services.cargowise_exporter import CargoWiseExporter
from app.services.entry_prep_service import EntryPrepData, EntryPrepService
from app.startup.client_access import (
    assert_user_can_access_client,
    is_broker_admin,
    is_broker_staff,
    portal_user_client_id,
)
from app.startup.hts_seed import STARTER_USITC_HTS_CODES


def test_scrypt_password_hashing_and_legacy_sha256_fallback():
    user = ClientUser(
        email="entrywriter@broker.com",
        first_name="Jane",
        last_name="Broker",
        client_id=uuid4(),
        role=ClientUserRole.BROKER_STAFF.value,
    )
    user.set_password("StrongCustomsPass!2026")
    assert user.password_hash.startswith("scrypt$16384$8$1$")
    assert not user.needs_password_rehash
    assert user.verify_password("StrongCustomsPass!2026")
    assert not user.verify_password("WrongPassword")

    # Verify seamless fallback for legacy <salt>:<sha256> hashes
    legacy_salt = secrets.token_hex(16)
    legacy_digest = hashlib.sha256(f"{legacy_salt}:LegacySecret99".encode("utf-8")).hexdigest()
    user.password_hash = f"{legacy_salt}:{legacy_digest}"
    assert user.needs_password_rehash
    assert user.verify_password("LegacySecret99")
    assert not user.verify_password("OtherSecret")


def test_role_separation_broker_staff_vs_client_admin():
    client_a = uuid4()
    client_b = uuid4()

    broker_admin = {"role": "admin", "client_id": str(client_a)}
    broker_writer = {"role": "broker_staff", "client_id": str(client_a)}
    importer_admin = {"role": "client_admin", "client_id": str(client_a)}

    assert is_broker_admin(broker_admin)
    assert is_broker_staff(broker_admin)
    assert not is_broker_admin(broker_writer)
    assert is_broker_staff(broker_writer)
    assert not is_broker_staff(importer_admin)

    # Broker entry writers can access multiple importer clients
    assert portal_user_client_id(broker_writer) is None
    asyncio.run(assert_user_can_access_client(broker_writer, client_b))

    # External Client Admin is strictly locked to their own importer client_id
    assert portal_user_client_id(importer_admin) == client_a
    asyncio.run(assert_user_can_access_client(importer_admin, client_a))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(assert_user_can_access_client(importer_admin, client_b))
    assert exc.value.status_code == 403


def test_entry_prep_never_injects_synthetic_hts_ior_or_value():
    entry = EntryPrepData()
    ext = ExtractionResult(
        field_name="cargo_item_1",
        field_value="Industrial Stainless Steel Valves",
        extraction_metadata={},  # Missing HTS, value, qty, origin
    )
    EntryPrepService._merge_extraction_data(entry, [ext], hts_rates={})
    EntryPrepService._calculate_duties(entry)
    EntryPrepService._validate_entry(entry)

    # Must NEVER fabricate 8471.30.0100, 94-3281940-00, CN, or $48,500.00
    assert entry.importer_of_record_number is None
    assert entry.country_of_origin is None
    assert entry.total_entered_value == Decimal("0.00")
    assert entry.total_mpf == Decimal("0.00")
    assert entry.line_items[0]["hts_number"] is None
    assert entry.line_items[0]["country_of_origin"] is None
    assert any("Missing Importer of Record EIN" in w for w in entry.validation_warnings)
    assert any("Missing 10-digit HTS classification" in w for w in entry.validation_warnings)


def test_entry_prep_fy2026_mpf_caps_and_verified_hts_rates():
    entry = EntryPrepData()
    ext = ExtractionResult(
        field_name="cargo_item_1",
        field_value="Cotton Knit T-Shirts",
        extraction_metadata={
            "hts_code": "6109.10.0012",
            "quantity": 500,
            "unit": "PCS",
            "country_of_origin": "VN",
            "total_value": "5000.00",
        },
    )
    EntryPrepService._merge_extraction_data(
        entry,
        [ext],
        hts_rates={"6109.10.0012": 0.165},
    )
    EntryPrepService._calculate_duties(entry)

    assert entry.line_items[0]["rate_verified"] is True
    assert entry.total_duty == Decimal("825.00")
    # 0.3464% of $5,000 is $17.32 -> clamped to FY2026 CBP minimum $33.58
    assert entry.total_mpf == Decimal("33.58")


def test_audit_retention_meets_cbp_19_cfr_163_five_year_minimum():
    assert AUDIT_LOG_RETENTION_DAYS >= 1825

    with pytest.raises(ValueError, match="19 CFR Part 163"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 64,
            SMTP_HOST="smtp.resend.com",
            RATE_LIMIT_STORAGE="redis://localhost:6379/2",
            AUDIT_LOG_RETENTION_DAYS=180,
        )


def test_cargowise_xml_uses_configured_broker_identifiers(monkeypatch):
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "cargowise_company_code", "HARBORBRK")
    monkeypatch.setattr(cfg_module.settings, "cargowise_enterprise_id", "HARBOR-CW1")

    dummy_entry = MagicMock()
    dummy_entry.entry_number = "HB1-1234567-8"
    dummy_entry.entry_type = "01"
    dummy_entry.port_of_entry = "4601"
    dummy_entry.port_of_unlading = "4601"
    dummy_entry.entry_date = None
    dummy_entry.import_date = None
    dummy_entry.bond_type = "8"
    dummy_entry.surety_code = "001"
    dummy_entry.bond_number = None
    dummy_entry.assigned_to = "writer@harborbrokerage.com"
    dummy_entry.importer_of_record_name = "Atlantic Goods LLC"
    dummy_entry.importer_of_record_number = "12-345678900"
    dummy_entry.ultimate_consignee_name = "Atlantic Goods LLC"
    dummy_entry.parties = []
    dummy_entry.mode_of_transport = "10"
    dummy_entry.carrier_code = "MAEU"
    dummy_entry.vessel_name = "MAERSK SEOUL"
    dummy_entry.voyage_flight_number = "412W"
    dummy_entry.bill_of_lading = "MAEU99887766"
    dummy_entry.master_bill = "MAEU99887766"
    dummy_entry.house_bill = None
    dummy_entry.foreign_port_of_lading = None
    dummy_entry.container_numbers = []
    dummy_entry.lines = []
    dummy_entry.total_entered_value = Decimal("10000.00")
    dummy_entry.total_dutiable_value = Decimal("10000.00")
    dummy_entry.total_duty = Decimal("250.00")
    dummy_entry.mpf_amount = Decimal("34.64")
    dummy_entry.hmf_amount = Decimal("12.50")
    dummy_entry.section_301_amount = Decimal("0.00")
    dummy_entry.section_232_amount = Decimal("0.00")
    dummy_entry.add_amount = Decimal("0.00")
    dummy_entry.cvd_amount = Decimal("0.00")
    dummy_entry.total_amount_due = Decimal("297.14")
    dummy_entry.currency = "USD"

    exporter = CargoWiseExporter(db=AsyncMock())
    xml_out = exporter._build_universal_shipment(dummy_entry)
    assert "<Code>HARBORBRK</Code>" in xml_out
    assert "<EnterpriseID>HARBOR-CW1</EnterpriseID>" in xml_out
    assert "GATE-CUSTOMS" not in xml_out


def test_starter_usitc_hts_seed_catalog_has_broad_coverage():
    assert len(STARTER_USITC_HTS_CODES) >= 50
    chapters = {row[2] for row in STARTER_USITC_HTS_CODES}
    for critical_chapter in (61, 62, 64, 73, 84, 85, 87, 90, 94):
        assert critical_chapter in chapters


def test_login_brute_force_lockout_triggers_429_and_resets():
    from app.api.routes.client_portal import (
        _assert_not_login_throttled,
        _clear_failed_login,
        _record_failed_login,
    )

    ip = "203.0.113.55"
    email = "attacker@broker.test"
    _clear_failed_login(ip, email)

    for _ in range(10):
        _assert_not_login_throttled(ip, email)
        _record_failed_login(ip, email)

    with pytest.raises(HTTPException) as exc:
        _assert_not_login_throttled(ip, email)
    assert exc.value.status_code == 429

    _clear_failed_login(ip, email)
    _assert_not_login_throttled(ip, email)


def test_celery_beat_registers_shared_inbox_monitor():
    from app.core.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "monitor-email-inbox" in schedule
    assert schedule["monitor-email-inbox"]["task"] == "email.monitor_inbox"


def test_api_key_scope_enforcement_blocks_write_and_admin_with_readonly_key():
    from app.middleware.auth import check_api_key_permission

    readonly_perms = ["entries:read", "shipments:read", "reference:read"]

    # Permitted read-only operations
    assert check_api_key_permission("GET", "/api/entries", readonly_perms) is None
    assert check_api_key_permission("GET", "/api/export/cargowise/123/download", readonly_perms) is None
    assert check_api_key_permission("GET", "/api/reference-data/hts/search", readonly_perms) is None

    # Blocked mutating & admin operations
    assert check_api_key_permission("POST", "/api/entries", readonly_perms) == "entries:write"
    assert check_api_key_permission("DELETE", "/api/shipments/123", readonly_perms) == "shipments:write"
    assert check_api_key_permission("GET", "/api/admin/dashboard", readonly_perms) == "broker_session_required"
    assert check_api_key_permission("PATCH", "/api/portal/users/123/role", readonly_perms) == "broker_session_required"


def test_isf_production_blocks_fake_cbp_transmission_when_simulation_disabled(monkeypatch):
    from app.core import config as cfg_module
    from app.services.isf_service import ISFService

    monkeypatch.setattr(cfg_module.settings, "environment", "production")
    monkeypatch.setattr(cfg_module.settings, "ace_sftp_enabled", False)
    monkeypatch.setattr(cfg_module.settings, "ace_allow_simulation", False)

    svc = ISFService(db=AsyncMock())
    fake_isf = MagicMock()
    fake_isf.isf_number = "ISF-001"
    fake_isf.is_flexible = False
    svc.get_isf = AsyncMock(return_value=fake_isf)
    svc.validate_isf = AsyncMock(return_value={"can_file": True})

    res = asyncio.run(svc.file_isf(uuid4()))
    assert res.get("mode") == "blocked"
    assert "error" in res


def test_ace_entry_file_and_poll_blocked_when_simulation_disabled(monkeypatch):
    from app.core import config as cfg_module
    from app.services.ace_status_service import ACEStatusService, ace_simulation_blocked

    monkeypatch.setattr(cfg_module.settings, "environment", "production")
    monkeypatch.setattr(cfg_module.settings, "ace_sftp_enabled", False)
    monkeypatch.setattr(cfg_module.settings, "ace_sftp_host", "")
    monkeypatch.setattr(cfg_module.settings, "ace_allow_simulation", False)

    assert ace_simulation_blocked() is not None

    svc = ACEStatusService(db=AsyncMock())
    filed = asyncio.run(svc.mark_filed(uuid4()))
    assert filed.get("mode") == "blocked"
    assert "error" in filed

    polled = asyncio.run(svc.simulate_ace_poll(uuid4()))
    assert polled.get("mode") == "blocked"
    assert "error" in polled


def test_storage_callback_refuses_insecure_fallback_in_production(monkeypatch):
    from app.api.routes import storage_callbacks
    from app.core import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "environment", "production")
    monkeypatch.setattr(cfg_module.settings, "storage_callback_secret", None)

    with pytest.raises(HTTPException) as exc:
        storage_callbacks.get_callback_secret()
    assert exc.value.status_code == 503


def test_cargowise_exporter_generates_7501_pdf_and_xlsx_artifacts():
    dummy_entry = MagicMock()
    dummy_entry.id = uuid4()
    dummy_entry.entry_number = "HB1-7654321-0"
    dummy_entry.entry_type = "01"
    dummy_entry.filer_code = "HB1"
    dummy_entry.port_of_entry = "2704"
    dummy_entry.port_of_unlading = "2704"
    dummy_entry.entry_date = None
    dummy_entry.import_date = None
    dummy_entry.release_date = None
    dummy_entry.bond_type = "8"
    dummy_entry.surety_code = "001"
    dummy_entry.bond_number = "BND9988"
    dummy_entry.mode_of_transport = "10"
    dummy_entry.carrier_code = "OOLU"
    dummy_entry.vessel_name = "OOCL TOKYO"
    dummy_entry.voyage_flight_number = "102E"
    dummy_entry.bill_of_lading = "OOLU456789123"
    dummy_entry.master_bill = "OOLU456789123"
    dummy_entry.house_bill = None
    dummy_entry.foreign_port_of_lading = "TWKHH"
    dummy_entry.importer_of_record_name = "Global Industrial Machinery Inc."
    dummy_entry.importer_of_record_number = "12-345678900"
    dummy_entry.ultimate_consignee_name = "Global Industrial Machinery Inc."
    dummy_entry.total_entered_value = Decimal("142800.00")
    dummy_entry.total_dutiable_value = Decimal("142800.00")
    dummy_entry.total_duty = Decimal("3570.00")
    dummy_entry.mpf_amount = Decimal("494.66")
    dummy_entry.hmf_amount = Decimal("178.50")
    dummy_entry.section_301_amount = Decimal("0.00")
    dummy_entry.section_232_amount = Decimal("0.00")
    dummy_entry.add_amount = Decimal("0.00")
    dummy_entry.cvd_amount = Decimal("0.00")
    dummy_entry.total_amount_due = Decimal("4243.16")
    dummy_entry.currency = "USD"
    dummy_entry.status = "draft"

    dummy_line = MagicMock()
    dummy_line.line_number = 1
    dummy_line.hts_code = "8479.89.9599"
    dummy_line.hts_description = "Industrial machinery NESOI"
    dummy_line.product_description = "CNC Assembly Unit"
    dummy_line.country_of_origin = "TW"
    dummy_line.quantity_1 = Decimal("4")
    dummy_line.uom_1 = "PCS"
    dummy_line.gross_weight = Decimal("1800")
    dummy_line.entered_value = Decimal("142800.00")
    dummy_line.duty_rate = Decimal("2.5")
    dummy_line.duty_amount = Decimal("3570.00")
    dummy_line.section_301_duty = Decimal("0.00")
    dummy_line.total_line_duty = Decimal("3570.00")
    dummy_line.fta_code = None
    dummy_entry.lines = [dummy_line]
    dummy_entry.parties = []

    exporter = CargoWiseExporter(db=AsyncMock())
    exporter._load_entry = AsyncMock(return_value=dummy_entry)

    pdf_bytes, pdf_name = asyncio.run(exporter.export_entry_pdf(str(dummy_entry.id)))
    assert pdf_bytes.startswith(b"%PDF-")
    assert pdf_name.endswith(".pdf")

    xlsx_bytes, xlsx_name = asyncio.run(exporter.export_entry_excel(str(dummy_entry.id)))
    assert xlsx_bytes.startswith(b"PK\x03\x04")
    assert xlsx_name.endswith(".xlsx")


