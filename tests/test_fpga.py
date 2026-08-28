from __future__ import annotations

import struct

import pytest

from pcb_inspector.fpga import MAP_SIZE, REG_VERSION, REG_WIDTH, UioRegisterMap


def test_uio_register_configuration(tmp_path) -> None:
    backing = tmp_path / "uio.bin"
    backing.write_bytes(b"\x00" * MAP_SIZE)
    with backing.open("r+b") as f:
        f.seek(REG_WIDTH)
        f.write(struct.pack("<I", 1280))
        f.seek(REG_VERSION)
        f.write(struct.pack("<I", 0x00020000))

    with UioRegisterMap(backing) as regs:
        regs.configure(sobel=True, threshold_enable=True, threshold=123)
        status = regs.status()

    assert status.sobel_enabled is True
    assert status.threshold_enabled is True
    assert status.threshold == 123
    assert status.image_width == 1280
    assert status.version_string == "2.0"


def test_uio_rejects_bad_threshold(tmp_path) -> None:
    backing = tmp_path / "uio.bin"
    backing.write_bytes(b"\x00" * MAP_SIZE)
    with UioRegisterMap(backing) as regs:
        with pytest.raises(ValueError):
            regs.configure(sobel=True, threshold_enable=False, threshold=300)


def test_uio_rejects_unaligned_offset(tmp_path) -> None:
    backing = tmp_path / "uio.bin"
    backing.write_bytes(b"\x00" * MAP_SIZE)
    with UioRegisterMap(backing) as regs:
        with pytest.raises(ValueError):
            regs.read32(1)
