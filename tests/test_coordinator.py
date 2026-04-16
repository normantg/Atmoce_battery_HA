"""Tests for AtmoceCoordinator computed sensors and control methods."""
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.atmoce.coordinator import AtmoceCoordinator


class TestComputedAutonomy:
    """Tests for the autonomy_hours derived sensor."""

    def test_autonomy_calculated_when_consuming(self, coordinator):
        data = {
            "battery_soc": 80,
            "pv_power": 0,
            "battery_power": -500,   # discharging 500 W
            "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        # 80% of 7 kWh = 5.6 kWh available; consumption ≈ 500 W → ~11.2 h
        assert result["autonomy_hours"] is not None
        assert result["autonomy_hours"] > 0

    def test_autonomy_none_when_consumption_too_low(self, coordinator):
        data = {
            "battery_soc": 80,
            "pv_power": 5,
            "battery_power": 0,
            "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        # avg consumption < 10 W → sensor unavailable
        assert result["autonomy_hours"] is None

    def test_autonomy_none_when_soc_zero(self, coordinator):
        data = {
            "battery_soc": 0,
            "pv_power": 0,
            "battery_power": -500,
            "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["autonomy_hours"] == 0.0

    def test_autonomy_uses_rolling_average(self, coordinator):
        # Feed several data points to build the rolling window
        for _ in range(10):
            coordinator._compute_derived({
                "battery_soc": 100,
                "pv_power": 0,
                "battery_power": -1000,
                "grid_power": 0,
            })
        result = coordinator._compute_derived({
            "battery_soc": 50,
            "pv_power": 0,
            "battery_power": -1000,
            "grid_power": 0,
        })
        # 50% of 7 kWh = 3.5 kWh; avg consumption ≈ 1000 W → 3.5 h
        assert result["autonomy_hours"] == pytest.approx(3.5, abs=0.5)


class TestComputedPvSelfConsumption:
    """Tests for the pv_self_consumption_rate derived sensor."""

    def test_full_self_consumption(self, coordinator):
        # All PV consumed locally, importing from grid (no export)
        # grid_power positive = importing, so exported = max(0, -positive) = 0
        data = {
            "battery_soc": 50, "battery_power": -1000,
            "pv_power": 2000, "grid_power": 500,
        }
        result = coordinator._compute_derived(data)
        assert result["pv_self_consumption_rate"] == 100.0

    def test_partial_export(self, coordinator):
        # 1000 W PV, exporting 400 W → 60% self-consumed
        # grid_power negative = exporting to grid
        data = {
            "battery_soc": 50, "battery_power": 0,
            "pv_power": 1000, "grid_power": -400,
        }
        result = coordinator._compute_derived(data)
        assert result["pv_self_consumption_rate"] == pytest.approx(60.0, abs=0.1)

    def test_full_export(self, coordinator):
        # All PV exported to grid (grid_power negative = exporting)
        data = {
            "battery_soc": 50, "battery_power": 0,
            "pv_power": 1000, "grid_power": -1000,
        }
        result = coordinator._compute_derived(data)
        assert result["pv_self_consumption_rate"] == pytest.approx(0.0, abs=0.1)

    def test_none_when_pv_too_low(self, coordinator):
        data = {
            "battery_soc": 50, "battery_power": 0,
            "pv_power": 5, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["pv_self_consumption_rate"] is None


class TestComputedBatteryHealthy:
    """Tests for the battery_healthy binary sensor."""

    def test_healthy_normal_operation(self, coordinator):
        data = {
            "battery_soc": 50, "pv_power": 500,
            "battery_power": 0, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["battery_healthy"] is True

    def test_unhealthy_soc_zero_with_pv(self, coordinator):
        # SOC stuck at 0 while PV > 100 W → likely a fault
        data = {
            "battery_soc": 0, "pv_power": 500,
            "battery_power": 0, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["battery_healthy"] is False

    def test_healthy_soc_zero_no_pv(self, coordinator):
        # SOC at 0 at night → normal (fully discharged)
        data = {
            "battery_soc": 0, "pv_power": 0,
            "battery_power": 0, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["battery_healthy"] is True

    def test_healthy_soc_100(self, coordinator):
        data = {
            "battery_soc": 100, "pv_power": 2000,
            "battery_power": 0, "grid_power": 0,
        }
        result = coordinator._compute_derived(data)
        assert result["battery_healthy"] is True


class TestComputedNoneValues:
    """Tests that None sensor values don't crash the coordinator."""

    def test_all_none_values(self, coordinator):
        data = {
            "battery_soc": None,
            "pv_power": None,
            "battery_power": None,
            "grid_power": None,
        }
        result = coordinator._compute_derived(data)
        assert result["autonomy_hours"] is None
        assert result["pv_self_consumption_rate"] is None
        assert result["battery_healthy"] is True  # None soc → 0, None pv → 0


class TestControlMethods:
    """Tests that control methods delegate correctly to the Modbus client."""

    @pytest.mark.asyncio
    async def test_set_remote_control_on(self, coordinator):
        await coordinator.async_set_remote_control(True)
        coordinator._modbus.async_set_remote_control.assert_awaited_once_with(True)

    @pytest.mark.asyncio
    async def test_set_remote_control_off(self, coordinator):
        await coordinator.async_set_remote_control(False)
        coordinator._modbus.async_set_remote_control.assert_awaited_once_with(False)

    @pytest.mark.asyncio
    async def test_set_forced_command(self, coordinator):
        await coordinator.async_set_forced_command(2)
        coordinator._modbus.async_set_forced_command.assert_awaited_once_with(2)

    @pytest.mark.asyncio
    async def test_set_forced_target_soc(self, coordinator):
        await coordinator.async_set_forced_target_soc(80)
        coordinator._modbus.async_set_forced_target_soc.assert_awaited_once_with(80)

    @pytest.mark.asyncio
    async def test_set_forced_duration(self, coordinator):
        await coordinator.async_set_forced_duration(120)
        coordinator._modbus.async_set_forced_duration.assert_awaited_once_with(120)

    @pytest.mark.asyncio
    async def test_reset_gateway(self, coordinator):
        await coordinator.async_reset_gateway()
        coordinator._modbus.async_reset_gateway.assert_awaited_once()
