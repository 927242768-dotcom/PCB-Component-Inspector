from __future__ import annotations

import mmap
import os
import struct
from dataclasses import dataclass
from pathlib import Path


REG_CONTROL = 0x00
REG_THRESHOLD = 0x04
REG_WIDTH = 0x08
REG_VERSION = 0x0C
MAP_SIZE = 0x1000


@dataclass(frozen=True)
class FpgaStatus:
    sobel_enabled: bool
    threshold_enabled: bool
    threshold: int
    image_width: int
    version: int

    @property
    def version_string(self) -> str:
        major = (self.version >> 16) & 0xFFFF
        minor = self.version & 0xFFFF
        return f"{major}.{minor}"


class UioRegisterMap:
    """通过 Linux UIO 暴露的 AXI-Lite/PCIe BAR 控制 FPGA 预处理核。

    真实板卡上通常传入 /dev/uio0；测试时也可传入普通 4 KiB 文件。
    图像数据面由 AXI4-Stream + VDMA/视频 DMA 完成，本类只负责控制面寄存器。
    """

    def __init__(self, device: str | os.PathLike[str] = "/dev/uio0", map_size: int = MAP_SIZE):
        self.device = Path(device)
        self.map_size = int(map_size)
        self._fd: int | None = None
        self._mm: mmap.mmap | None = None

    def open(self) -> "UioRegisterMap":
        if self._mm is not None:
            return self
        # Linux UIO 使用 O_SYNC；Windows 仅用于普通文件模拟测试，不提供该标志。
        sync_flag = getattr(os, "O_SYNC", 0)
        self._fd = os.open(self.device, os.O_RDWR | sync_flag)
        self._mm = mmap.mmap(self._fd, self.map_size, access=mmap.ACCESS_WRITE)
        return self

    def close(self) -> None:
        if self._mm is not None:
            self._mm.close()
            self._mm = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "UioRegisterMap":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _require_open(self) -> mmap.mmap:
        if self._mm is None:
            raise RuntimeError("FPGA 寄存器尚未打开")
        return self._mm

    def read32(self, offset: int) -> int:
        mm = self._require_open()
        if offset < 0 or offset + 4 > self.map_size or offset % 4:
            raise ValueError(f"非法寄存器偏移：0x{offset:x}")
        return struct.unpack_from("<I", mm, offset)[0]

    def write32(self, offset: int, value: int) -> None:
        mm = self._require_open()
        if offset < 0 or offset + 4 > self.map_size or offset % 4:
            raise ValueError(f"非法寄存器偏移：0x{offset:x}")
        struct.pack_into("<I", mm, offset, value & 0xFFFFFFFF)
        mm.flush()

    def configure(self, *, sobel: bool, threshold_enable: bool, threshold: int = 96) -> None:
        if not 0 <= threshold <= 255:
            raise ValueError("threshold 必须在 0~255")
        control = (1 if sobel else 0) | ((1 if threshold_enable else 0) << 1)
        self.write32(REG_THRESHOLD, threshold)
        self.write32(REG_CONTROL, control)

    def status(self) -> FpgaStatus:
        control = self.read32(REG_CONTROL)
        return FpgaStatus(
            sobel_enabled=bool(control & 0x1),
            threshold_enabled=bool(control & 0x2),
            threshold=self.read32(REG_THRESHOLD) & 0xFF,
            image_width=self.read32(REG_WIDTH),
            version=self.read32(REG_VERSION),
        )
