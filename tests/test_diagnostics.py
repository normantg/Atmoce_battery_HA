"""Tests for diagnostics export."""
from unittest.mock import MagicMock

import pytest

from custom_components.atmoce.diagnostics import async_get_config_entry_diagnostics
from custom_components.atmoce.const import CONF_CLOUD_APP_KEY, CONF_CLOUD_APP_SECRET, DOMAIN


def _make_hass_and_entry(data: dict):
    coordinator = MagicMock()
    coordinator.active_source = "Modbus"
    coordinator.connection_errors = 0
    coordinator.serial_number = "SN123456"
    coordinator.firmware_version = "1.0.0"
    coordinator.hw_version = 1
    coordinator.battery_model = "MS-7K-U"
    coordinator.capacity_kwh = 7.0
    coordinator.max_charge_kw = 3.75
    coordinator.max_discharge_kw = 4.5
    coordinator.data = {"battery_soc": 80, "pv_power": 1500}

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = data

    hass = MagicMock()
    hass.data = {DOMAIN: {"test_entry": coordinator}}

    return hass, entry


class TestDiagnosticsRedaction:
    @pytest.mark.asyncio
    async def test_cloud_credentials_are_redacted(self):
        data = {
            "host": "192.168.1.100",
            CONF_CLOUD_APP_KEY: "my-secret-key",
            CONF_CLOUD_APP_SECRET: "my-secret-value",
        }
        hass, entry = _make_hass_and_entry(data)
        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["config_entry"][CONF_CLOUD_APP_KEY] == "**REDACTED**"
        assert result["config_entry"][CONF_CLOUD_APP_SECRET] == "**REDACTED**"

    @pytest.mark.asyncio
    async def test_host_is_not_redacted(self):
        data = {"host": "192.168.1.100", CONF_CLOUD_APP_KEY: "key"}
        hass, entry = _make_hass_and_entry(data)
        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["config_entry"]["host"] == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_missing_credentials_dont_crash(self):
        # Entry without cloud credentials
        data = {"host": "192.168.1.100"}
        hass, entry = _make_hass_and_entry(data)
        result = await async_get_config_entry_diagnostics(hass, entry)

        assert CONF_CLOUD_APP_KEY not in result["config_entry"]

    @pytest.mark.asyncio
    async def test_coordinator_info_included(self):
        data = {"host": "192.168.1.100"}
        hass, entry = _make_hass_and_entry(data)
        result = await async_get_config_entry_diagnostics(hass, entry)

        coord_info = result["coordinator"]
        assert coord_info["active_source"] == "Modbus"
        assert coord_info["serial_number"] == "SN123456"
        assert coord_info["battery_model"] == "MS-7K-U"
        assert coord_info["capacity_kwh"] == 7.0

    @pytest.mark.asyncio
    async def test_last_data_included(self):
        data = {"host": "192.168.1.100"}
        hass, entry = _make_hass_and_entry(data)
        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["last_data"]["battery_soc"] == 80
        assert result["last_data"]["pv_power"] == 1500
