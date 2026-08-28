from __future__ import annotations

import struct

import pytest

from pcb_inspector.fpga import (
    MAP_SIZE,
    PANGO100H_SIGNATURE,
    PANGO_CFG_BINARY,
    PANGO_CFG_GAUSSIAN,
    PANGO_CFG_SOBEL,
    REG_VERSION,
    REG_WIDTH,
    Pango100HPreprocessClient,
    PcieBarRegion,
    UioRegisterMap,
)


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


def test_pango100h_cfg_and_frame_size() -> None:
    cfg = Pango100HPreprocessClient.build_cfg(gaussian=True, sobel=True, binary=True)
    assert cfg & PANGO_CFG_GAUSSIAN
    assert cfg & PANGO_CFG_SOBEL
    assert cfg & PANGO_CFG_BINARY
    Pango100HPreprocessClient.validate_frame_size(112, 64)
    with pytest.raises(ValueError):
        Pango100HPreprocessClient.validate_frame_size(111, 64)
    with pytest.raises(ValueError):
        Pango100HPreprocessClient.validate_frame_size(128, 100)


def test_pango100h_status_parser() -> None:
    dwords = [
        PANGO100H_SIGNATURE,
        0b1010,
        (64 << 16) | 112,
        7,
        (0x001C << 8) | 96,
        0,
        0,
        7168,
        1234,
        7936,
        0x02000001,
        0x1C,
    ]
    status = Pango100HPreprocessClient.parse_status(struct.pack("<12I", *dwords))
    assert status.done is True
    assert status.continuous is True
    assert status.busy is False
    assert status.width == 112
    assert status.height == 64
    assert status.frame_counter == 7
    assert status.threshold == 96
    assert status.preprocess_cfg == 0x001C
    assert status.frame_capacity == 7936


def test_pcie_bar_region_file_backing(tmp_path) -> None:
    backing = tmp_path / "resource0"
    backing.write_bytes(b"\x00" * 4096)
    with PcieBarRegion(backing, 4096) as bar:
        bar.write32(0x100, 0x12345678)
        assert bar.read32(0x100) == 0x12345678
        with pytest.raises(ValueError):
            bar.read(4090, 16)
