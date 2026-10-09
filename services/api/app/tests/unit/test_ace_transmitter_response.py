"""
Tests for Task A — ACETransmitter.check_response() + _fetch_sftp_response_file()
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.ace_transmitter import (
    ACETransmitter,
    TransmissionMode,
    TransmissionStatus,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_entry(entry_number="ABCD-1234567-3", status="filing"):
    ent = SimpleNamespace(
        id=uuid4(),
        entry_number=entry_number,
        status=status,
        ace_entry_id="ACE-CONFIRM-001",
        updated_at=datetime.now(timezone.utc),
    )
    return ent


def _build_transmitter(mode=TransmissionMode.LIVE):
    """Return a transmitter with a mocked DB session."""
    db = MagicMock()
    tx = ACETransmitter.__new__(ACETransmitter)
    tx.db = db
    tx.mode = mode
    tx.sftp_host = "sftp.cbp.dhs.gov"
    tx.sftp_port = 22
    tx.sftp_user = "broker"
    tx.sftp_key_path = None
    tx.upload_path = "/upload"
    tx.response_path = "/response"
    return tx


# ---------------------------------------------------------------------------
# check_response — SIMULATION mode
# ---------------------------------------------------------------------------

class TestCheckResponseSimulation:
    @pytest.mark.asyncio
    async def test_simulation_returns_confirmed(self):
        tx = _build_transmitter(TransmissionMode.SIMULATION)
        entry = make_entry()

        # Mock DB query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        tx.db.execute = AsyncMock(return_value=mock_result)

        result = await tx.check_response(entry.id)

        assert result.success is True
        assert result.status == TransmissionStatus.CONFIRMED
        assert "SIMULATION" in result.message

    @pytest.mark.asyncio
    async def test_simulation_entry_not_found_returns_failed(self):
        tx = _build_transmitter(TransmissionMode.SIMULATION)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        tx.db.execute = AsyncMock(return_value=mock_result)

        result = await tx.check_response(uuid4())
        assert result.success is False
        assert result.status == TransmissionStatus.FAILED


# ---------------------------------------------------------------------------
# check_response — LIVE mode
# ---------------------------------------------------------------------------

class TestCheckResponseLive:
    @pytest.mark.asyncio
    async def test_live_no_sftp_file_returns_pending(self):
        tx = _build_transmitter(TransmissionMode.LIVE)
        entry = make_entry()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        tx.db.execute = AsyncMock(return_value=mock_result)

        # _fetch_sftp_response_file returns None → no file yet
        with patch.object(tx, "_fetch_sftp_response_file", new=AsyncMock(return_value=None)):
            result = await tx.check_response(entry.id)

        assert result.status == TransmissionStatus.PENDING
        assert "no file found yet" in result.message.lower()

    @pytest.mark.asyncio
    async def test_live_ae_code_returns_confirmed(self):
        tx = _build_transmitter(TransmissionMode.LIVE)
        entry = make_entry()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        tx.db.execute = AsyncMock(return_value=mock_result)
        tx.db.commit = AsyncMock()

        # Fake a parsed AE response
        raw = "AE ENTRY ABCD-1234567-3 ACCEPTED"
        with patch.object(tx, "_fetch_sftp_response_file", new=AsyncMock(return_value=raw)):
            with patch.object(tx, "_advance_entry_status", new=AsyncMock()):
                result = await tx.check_response(entry.id)

        assert result.status == TransmissionStatus.CONFIRMED
        assert result.success is True

    @pytest.mark.asyncio
    async def test_live_rj_code_returns_failed(self):
        tx = _build_transmitter(TransmissionMode.LIVE)
        entry = make_entry()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        tx.db.execute = AsyncMock(return_value=mock_result)
        tx.db.commit = AsyncMock()

        raw = "RJ ENTRY ABCD-1234567-3 REJECTED missing importer"
        with patch.object(tx, "_fetch_sftp_response_file", new=AsyncMock(return_value=raw)):
            with patch.object(tx, "_advance_entry_status", new=AsyncMock()):
                result = await tx.check_response(entry.id)

        assert result.status == TransmissionStatus.FAILED
        assert result.success is False


# ---------------------------------------------------------------------------
# _fetch_sftp_response_file
# ---------------------------------------------------------------------------

class TestFetchSftpResponseFile:
    @pytest.mark.asyncio
    async def test_returns_none_when_paramiko_missing(self):
        tx = _build_transmitter()
        with patch("app.services.ace_transmitter.paramiko", None):
            result = await tx._fetch_sftp_response_file("ABCD-1234567-3")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_matching_file(self):
        tx = _build_transmitter()
        mock_sftp = MagicMock()
        mock_sftp.listdir.return_value = ["OTHER_ENTRY_8765.txt"]
        mock_ssh = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp

        with patch("app.services.ace_transmitter.paramiko") as p:
            p.SSHClient.return_value = mock_ssh
            p.AutoAddPolicy = MagicMock
            result = await tx._fetch_sftp_response_file("ABCD1234567")

        assert result is None


# ---------------------------------------------------------------------------
# _advance_entry_status
# ---------------------------------------------------------------------------

class TestAdvanceEntryStatus:
    @pytest.mark.asyncio
    async def test_updates_status_for_non_final_entry(self):
        tx = _build_transmitter()
        tx.db.commit = AsyncMock()

        entry = make_entry(status="filing")
        await tx._advance_entry_status(entry, "released", "CBP AE accepted")

        assert entry.status == "released"
        tx.db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_update_for_released_entry(self):
        tx = _build_transmitter()
        tx.db.commit = AsyncMock()

        entry = make_entry(status="released")
        await tx._advance_entry_status(entry, "filed", "Should not regress")

        # Must NOT change status
        assert entry.status == "released"
        tx.db.commit.assert_not_awaited()
