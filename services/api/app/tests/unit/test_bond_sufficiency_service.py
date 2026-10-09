"""
Unit tests — Bond Sufficiency Alert Service  (Task 1.4)
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


def make_bond(bond_amount, current_utilization, bond_number="BOND-001", status="active"):
    bond = MagicMock()
    bond.id = "bond-uuid-001"
    bond.bond_number = bond_number
    bond.bond_amount = Decimal(str(bond_amount))
    bond.current_utilization = Decimal(str(current_utilization))
    bond.status = status
    return bond


@pytest.fixture
def db():
    return AsyncMock()


@pytest.fixture
def service(db):
    from app.services.bond_sufficiency_service import BondSufficiencyService
    return BondSufficiencyService(db)


class TestBondUtilisationCalculation:

    def test_zero_utilisation(self, service):
        bond = make_bond(bond_amount=100_000, current_utilization=0)
        u = service.calculate_utilisation(bond)
        assert u == Decimal("0.0000")

    def test_80_percent_utilisation(self, service):
        bond = make_bond(bond_amount=100_000, current_utilization=80_000)
        u = service.calculate_utilisation(bond)
        assert u == Decimal("0.8000")

    def test_100_percent_utilisation(self, service):
        bond = make_bond(bond_amount=50_000, current_utilization=50_000)
        u = service.calculate_utilisation(bond)
        assert u == Decimal("1.0000")

    def test_no_bond_amount_returns_none(self, service):
        bond = make_bond(bond_amount=0, current_utilization=0)
        assert service.calculate_utilisation(bond) is None

    def test_remaining_capacity(self, service):
        bond = make_bond(bond_amount=100_000, current_utilization=75_000)
        remaining = service.get_remaining_capacity(bond)
        assert remaining == Decimal("25000")


class TestBondSufficiencyThresholds:

    def test_below_warning_threshold_is_sufficient(self, service):
        bond = make_bond(bond_amount=100_000, current_utilization=70_000)  # 70%
        assert service.is_sufficient(bond) is True

    def test_at_warning_threshold_not_sufficient(self, service):
        bond = make_bond(bond_amount=100_000, current_utilization=80_000)  # 80%
        assert service.is_sufficient(bond) is False

    def test_above_critical_threshold(self, service):
        bond = make_bond(bond_amount=100_000, current_utilization=96_000)  # 96%
        from app.services.bond_sufficiency_service import CRITICAL_THRESHOLD
        u = service.calculate_utilisation(bond)
        assert u >= CRITICAL_THRESHOLD

    def test_no_bond_amount_is_sufficient(self, service):
        """Bonds without an amount set are treated as unconfigured (not dangerous)."""
        bond = make_bond(bond_amount=0, current_utilization=0)
        assert service.is_sufficient(bond) is True


class TestBondSufficiencyScanner:

    @pytest.mark.asyncio
    async def test_no_bonds_returns_zeros(self, service, db):
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
        )
        result = await service.check_all_bonds()
        assert result["bonds_checked"] == 0
        assert result["warnings"] == 0
        assert result["criticals"] == 0

    @pytest.mark.asyncio
    async def test_warning_bond_detected(self, service, db):
        warn_bond = make_bond(bond_amount=100_000, current_utilization=82_000)  # 82%
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[warn_bond]))))
        )
        with patch.object(service, "_emit_alert", new_callable=AsyncMock):
            result = await service.check_all_bonds()
        assert result["warnings"] == 1
        assert result["criticals"] == 0

    @pytest.mark.asyncio
    async def test_critical_bond_detected(self, service, db):
        crit_bond = make_bond(bond_amount=100_000, current_utilization=97_000)  # 97%
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[crit_bond]))))
        )
        with patch.object(service, "_emit_alert", new_callable=AsyncMock):
            result = await service.check_all_bonds()
        assert result["criticals"] == 1
        assert result["warnings"] == 0

    @pytest.mark.asyncio
    async def test_healthy_bond_no_alert(self, service, db):
        healthy_bond = make_bond(bond_amount=100_000, current_utilization=50_000)  # 50%
        db.execute = AsyncMock(
            return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[healthy_bond]))))
        )
        with patch.object(service, "_emit_alert", new_callable=AsyncMock) as mock_emit:
            result = await service.check_all_bonds()
        mock_emit.assert_not_called()
        assert result["warnings"] == 0
        assert result["criticals"] == 0
