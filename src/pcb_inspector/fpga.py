from __future__ import annotations

import mmap
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# 通用 UIO/AXI-Lite 控制接口（保留兼容）
# ---------------------------------------------------------------------------
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
    """通用 UIO/MMIO 控制接口；100H 实机优先使用 Pango100HPreprocessClient。"""

    def __init__(self, device: str | os.PathLike[str] = "/dev/uio0", map_size: int = MAP_SIZE):
        self.device = Path(device)
        self.map_size = int(map_size)
        self._fd: int | None = None
        self._mm: mmap.mmap | None = None

    def open(self) -> "UioRegisterMap":
        if self._mm is not None:
            return self
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


# ---------------------------------------------------------------------------
# 紫光同创 PG2L100H + RK3568 PCIe BAR0 实机接口
# ---------------------------------------------------------------------------
PANGO100H_PCI_DEVICE = "0002:21:00.0"
PANGO100H_RESOURCE_ROOT = f"/sys/bus/pci/devices/{PANGO100H_PCI_DEVICE}"
PANGO100H_BAR_BYTES = 64 * 1024
PANGO100H_FRAME_OFFSET = 0x100
PANGO100H_SAFE_FRAME_BYTES = 7936
PANGO100H_DEFAULT_WIDTH = 112
PANGO100H_DEFAULT_HEIGHT = 64
PANGO100H_SIGNATURE = 0x50434250  # "PCBP"

PANGO_REG_CONTROL = 0x000
PANGO_REG_WIDTH = 0x010
PANGO_REG_HEIGHT = 0x020
PANGO_REG_THRESHOLD = 0x030
PANGO_REG_ROI_XY = 0x040
PANGO_REG_ROI_WH = 0x050
PANGO_REG_PREPROC_CFG = 0x060
PANGO_REG_FRAME_BYTES = 0x070

PANGO_CFG_INVERT = 1 << 0
PANGO_CFG_PASSTHROUGH = 1 << 1
PANGO_CFG_SOBEL = 1 << 2
PANGO_CFG_BINARY = 1 << 3
PANGO_CFG_GAUSSIAN = 1 << 4

PANGO_STATUS_BUSY = 1 << 0
PANGO_STATUS_DONE = 1 << 1
PANGO_STATUS_ERROR = 1 << 2
PANGO_STATUS_CONTINUOUS = 1 << 3


class PcieBarRegion:
    """Linux sysfs PCIe resourceN 的 mmap 封装。"""

    def __init__(self, path: str | os.PathLike[str], size: int = PANGO100H_BAR_BYTES):
        self.path = Path(path)
        self.size = int(size)
        self._fd: int | None = None
        self._mm: mmap.mmap | None = None

    def open(self) -> "PcieBarRegion":
        if self._mm is not None:
            return self
        sync_flag = getattr(os, "O_SYNC", 0)
        self._fd = os.open(self.path, os.O_RDWR | sync_flag)
        self._mm = mmap.mmap(self._fd, self.size, access=mmap.ACCESS_WRITE)
        return self

    def close(self) -> None:
        if self._mm is not None:
            self._mm.close()
            self._mm = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "PcieBarRegion":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _require_open(self) -> mmap.mmap:
        if self._mm is None:
            raise RuntimeError("PCIe BAR 尚未打开")
        return self._mm

    def _check_range(self, offset: int, size: int) -> None:
        if offset < 0 or size < 0 or offset + size > self.size:
            raise ValueError(f"BAR 越界: offset=0x{offset:x}, size={size}")

    def read(self, offset: int, size: int) -> bytes:
        self._check_range(offset, size)
        mm = self._require_open()
        mm.seek(offset)
        return mm.read(size)

    def write(self, offset: int, data: bytes) -> None:
        self._check_range(offset, len(data))
        mm = self._require_open()
        mm.seek(offset)
        mm.write(data)
        mm.flush()

    def read32(self, offset: int) -> int:
        return struct.unpack("<I", self.read(offset, 4))[0]

    def write32(self, offset: int, value: int) -> None:
        self.write(offset, struct.pack("<I", value & 0xFFFFFFFF))


@dataclass(frozen=True)
class Pango100HStatus:
    busy: bool
    done: bool
    error: bool
    continuous: bool
    width: int
    height: int
    frame_counter: int
    threshold: int
    preprocess_cfg: int
    roi: tuple[int, int, int, int]
    frame_bytes: int
    active_pixels: int
    frame_capacity: int
    abi_version: int
    feature_bits: int

    @property
    def active_ratio(self) -> float:
        return self.active_pixels / self.frame_bytes if self.frame_bytes else 0.0


class Pango100HPreprocessClient:
    """PG2L100H + RK3568 的单 BAR0 图像预处理客户端。

    ARM 将 112x64 uint8 灰度帧写入 resource0 的 0x100 起始窗口，
    FPGA 执行 Gaussian/Sobel/threshold 后，再从同一窗口读回掩码。
    """

    def __init__(
        self,
        resource_root: str | os.PathLike[str] = PANGO100H_RESOURCE_ROOT,
        *,
        bar_size: int = PANGO100H_BAR_BYTES,
    ) -> None:
        root = Path(resource_root)
        self.resource_root = root
        self.resource0 = root if root.name == "resource0" else root / "resource0"
        self.bar = PcieBarRegion(self.resource0, bar_size)
        self.current_shape: Optional[tuple[int, int]] = None
        self.current_cfg = 0
        self.current_continuous = False

    def open(self) -> "Pango100HPreprocessClient":
        self.bar.open()
        return self

    def close(self) -> None:
        self.bar.close()

    def __enter__(self) -> "Pango100HPreprocessClient":
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def build_cfg(
        *,
        gaussian: bool = True,
        sobel: bool = True,
        binary: bool = True,
        passthrough: bool = False,
        invert: bool = False,
    ) -> int:
        cfg = 0
        if invert:
            cfg |= PANGO_CFG_INVERT
        if passthrough:
            cfg |= PANGO_CFG_PASSTHROUGH
        if sobel:
            cfg |= PANGO_CFG_SOBEL
        if binary:
            cfg |= PANGO_CFG_BINARY
        if gaussian:
            cfg |= PANGO_CFG_GAUSSIAN
        return cfg

    @staticmethod
    def validate_frame_size(width: int, height: int) -> None:
        frame_bytes = int(width) * int(height)
        if width <= 0 or height <= 0:
            raise ValueError("FPGA 帧尺寸必须大于 0")
        if width % 16:
            raise ValueError("PG2L100H BAR0 预处理要求宽度是 16 的整数倍")
        if frame_bytes > PANGO100H_SAFE_FRAME_BYTES:
            raise ValueError(
                f"当前 100H 安全帧区为 {PANGO100H_SAFE_FRAME_BYTES} bytes，"
                f"请求 {width}x{height}={frame_bytes} bytes"
            )

    def configure(
        self,
        *,
        width: int = PANGO100H_DEFAULT_WIDTH,
        height: int = PANGO100H_DEFAULT_HEIGHT,
        threshold: int = 96,
        preprocess_cfg: int | None = None,
        roi: tuple[int, int, int, int] = (0, 0, 0, 0),
        continuous: bool = False,
    ) -> None:
        self.validate_frame_size(width, height)
        if not 0 <= threshold <= 255:
            raise ValueError("threshold 必须在 0~255")
        x, y, w, h = roi
        if min(x, y, w, h) < 0 or max(x, y, w, h) > 0xFFFF:
            raise ValueError("ROI 参数必须在 0~65535")
        cfg = self.build_cfg() if preprocess_cfg is None else int(preprocess_cfg) & 0xFFFF

        self.bar.write32(PANGO_REG_WIDTH, width)
        self.bar.write32(PANGO_REG_HEIGHT, height)
        self.bar.write32(PANGO_REG_THRESHOLD, threshold)
        self.bar.write32(PANGO_REG_ROI_XY, (y << 16) | x)
        self.bar.write32(PANGO_REG_ROI_WH, (h << 16) | w)
        self.bar.write32(PANGO_REG_PREPROC_CFG, cfg)
        self.bar.write32(PANGO_REG_FRAME_BYTES, width * height)
        self.bar.write32(PANGO_REG_CONTROL, (1 << 2) | ((1 << 1) if continuous else 0))

        self.current_shape = (height, width)
        self.current_cfg = cfg
        self.current_continuous = bool(continuous)

    def write_grayscale_frame(self, gray: np.ndarray) -> None:
        if gray.dtype != np.uint8 or gray.ndim != 2:
            raise ValueError("FPGA 输入必须是二维 uint8 灰度图")
        height, width = gray.shape
        self.validate_frame_size(width, height)
        if self.current_shape is not None and self.current_shape != (height, width):
            raise ValueError(f"输入尺寸 {width}x{height} 与已配置 FPGA 尺寸不一致")
        payload = gray.reshape(-1).tobytes()
        padding = (-len(payload)) % 16
        if padding:
            payload += b"\x00" * padding
        self.bar.write(PANGO100H_FRAME_OFFSET, payload)

    def start(self) -> None:
        control = 1 | ((1 << 1) if self.current_continuous else 0)
        self.bar.write32(PANGO_REG_CONTROL, control)

    @staticmethod
    def parse_status(raw: bytes) -> Pango100HStatus:
        if len(raw) < 48:
            raise ValueError("状态头至少需要 48 bytes")
        d = struct.unpack("<12I", raw[:48])
        if d[0] != PANGO100H_SIGNATURE:
            raise RuntimeError(
                f"PG2L100H BAR0 状态签名错误: 0x{d[0]:08x}，"
                f"期望 0x{PANGO100H_SIGNATURE:08x}"
            )
        bits = d[1]
        return Pango100HStatus(
            busy=bool(bits & PANGO_STATUS_BUSY),
            done=bool(bits & PANGO_STATUS_DONE),
            error=bool(bits & PANGO_STATUS_ERROR),
            continuous=bool(bits & PANGO_STATUS_CONTINUOUS),
            width=d[2] & 0xFFFF,
            height=(d[2] >> 16) & 0xFFFF,
            frame_counter=d[3],
            threshold=d[4] & 0xFF,
            preprocess_cfg=(d[4] >> 8) & 0xFFFF,
            roi=(d[5] & 0xFFFF, (d[5] >> 16) & 0xFFFF, d[6] & 0xFFFF, (d[6] >> 16) & 0xFFFF),
            frame_bytes=d[7],
            active_pixels=d[8],
            frame_capacity=d[9],
            abi_version=d[10],
            feature_bits=d[11],
        )

    def status(self) -> Pango100HStatus:
        return self.parse_status(self.bar.read(0, 48))

    def ensure_signature(self) -> Pango100HStatus:
        return self.status()

    def wait_done(self, timeout_s: float = 0.5, poll_interval_s: float = 0.002) -> Pango100HStatus:
        deadline = time.monotonic() + timeout_s
        last: Pango100HStatus | None = None
        while time.monotonic() < deadline:
            last = self.status()
            if last.error:
                raise RuntimeError("PG2L100H 图像预处理核返回 error 状态")
            if last.done and not last.busy:
                return last
            time.sleep(poll_interval_s)
        raise TimeoutError(f"等待 PG2L100H 完成超时，最后状态: {last}")

    def read_output(self, width: int | None = None, height: int | None = None) -> np.ndarray:
        if width is None or height is None:
            if self.current_shape is None:
                raise RuntimeError("尚未配置 FPGA 帧尺寸")
            height, width = self.current_shape
        self.validate_frame_size(int(width), int(height))
        raw = self.bar.read(PANGO100H_FRAME_OFFSET, int(width) * int(height))
        return np.frombuffer(raw, dtype=np.uint8).reshape(int(height), int(width)).copy()

    def process(self, gray: np.ndarray, *, timeout_s: float = 0.5) -> tuple[np.ndarray, Pango100HStatus]:
        self.write_grayscale_frame(gray)
        self.start()
        status = self.wait_done(timeout_s=timeout_s)
        return self.read_output(gray.shape[1], gray.shape[0]), status
