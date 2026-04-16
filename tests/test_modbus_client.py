"""Tests for Modbus register parsing helpers."""
import struct

import pytest

from custom_components.atmoce.modbus_client import (
    _regs_to_int32,
    _regs_to_str,
    _regs_to_uint32,
    _regs_to_uint64,
)


class TestRegsToUint32:
    def test_zero(self):
        assert _regs_to_uint32([0x0000, 0x0000]) == 0

    def test_max(self):
        assert _regs_to_uint32([0xFFFF, 0xFFFF]) == 0xFFFFFFFF

    def test_typical_power_value(self):
        # 3500 W → 0x00000DAC
        assert _regs_to_uint32([0x0000, 0x0DAC]) == 3500

    def test_high_word(self):
        # Value entirely in the high register
        assert _regs_to_uint32([0x0001, 0x0000]) == 65536

    def test_split_value(self):
        assert _regs_to_uint32([0x0001, 0x0001]) == 65537


class TestRegsToInt32:
    def test_zero(self):
        assert _regs_to_int32([0x0000, 0x0000]) == 0

    def test_positive(self):
        # 3500 W charging
        assert _regs_to_int32([0x0000, 0x0DAC]) == 3500

    def test_negative(self):
        # -3500 W discharging (two's complement)
        raw = struct.unpack(">HH", struct.pack(">i", -3500))
        assert _regs_to_int32(list(raw)) == -3500

    def test_minus_one(self):
        assert _regs_to_int32([0xFFFF, 0xFFFF]) == -1

    def test_min_int32(self):
        # -2147483648
        assert _regs_to_int32([0x8000, 0x0000]) == -2147483648

    def test_max_int32(self):
        # 2147483647
        assert _regs_to_int32([0x7FFF, 0xFFFF]) == 2147483647


class TestRegsToUint64:
    def test_zero(self):
        assert _regs_to_uint64([0, 0, 0, 0]) == 0

    def test_small_value(self):
        # 1 in the lowest register
        assert _regs_to_uint64([0, 0, 0, 1]) == 1

    def test_typical_energy(self):
        # 10000 kWh total (stored as 1000000 with scale 0.01) → 0xF4240
        assert _regs_to_uint64([0x0000, 0x0000, 0x000F, 0x4240]) == 1000000

    def test_high_registers(self):
        # Value in the highest register
        assert _regs_to_uint64([0x0001, 0x0000, 0x0000, 0x0000]) == 2**48


class TestRegsToStr:
    def test_simple_ascii(self):
        # "AB" → 0x4142
        assert _regs_to_str([0x4142]) == "AB"

    def test_serial_number(self):
        # "SN001" packed as registers
        raw = "SN001\x00\x00\x00\x00\x00"
        regs = [struct.unpack(">H", raw[i:i+2].encode("ascii"))[0] for i in range(0, len(raw), 2)]
        assert _regs_to_str(regs) == "SN001"

    def test_strips_null_bytes(self):
        # String with trailing nulls
        assert _regs_to_str([0x4100, 0x0000]) == "A"

    def test_strips_whitespace(self):
        # String with trailing spaces
        assert _regs_to_str([0x4120]) == "A"

    def test_empty(self):
        assert _regs_to_str([0x0000, 0x0000]) == ""
