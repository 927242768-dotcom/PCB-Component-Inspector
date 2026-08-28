from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

import numpy as np

from .detector import ComponentDetector, Detection
from .visualize import draw_detections


@dataclass(frozen=True)
class FrameInferenceSettings:
    """视频逐帧推理参数。"""

    conf: float = 0.25
    iou: float = 0.45
    imgsz: int = 640
    tile_size: int | None = None
    tile_overlap: float = 0.20


class FrameDetectionPipeline:
    """面向视频/摄像头的线程安全逐帧检测流水线。

    detect_every 用于控制检测频率。例如 detect_every=2 表示每 2 帧执行一次
    YOLO 推理，中间帧沿用最近一次检测框，从而降低 CPU/GPU 压力。
    """

    def __init__(
        self,
        detector: ComponentDetector,
        settings: FrameInferenceSettings,
        *,
        detect_every: int = 1,
    ) -> None:
        if detect_every < 1:
            raise ValueError("detect_every 必须大于等于 1")
        self.detector = detector
        self.settings = settings
        self.detect_every = int(detect_every)
        self._frame_index = 0
        self._has_inferred = False
        self._last_detections: list[Detection] = []
        self._lock = Lock()

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def last_detections(self) -> list[Detection]:
        with self._lock:
            return list(self._last_detections)

    def process(self, frame: np.ndarray) -> tuple[np.ndarray, list[Detection]]:
        """检测并标注一帧 BGR 图像，返回标注帧与当前检测结果。"""
        if frame is None or frame.size == 0:
            raise ValueError("视频帧为空")

        with self._lock:
            should_detect = not self._has_inferred or self._frame_index % self.detect_every == 0
            if should_detect:
                self._last_detections = self.detector.predict(
                    frame,
                    conf=self.settings.conf,
                    iou=self.settings.iou,
                    imgsz=self.settings.imgsz,
                    tile_size=self.settings.tile_size,
                    tile_overlap=self.settings.tile_overlap,
                )
                self._has_inferred = True

            detections = list(self._last_detections)
            self._frame_index += 1

        annotated = draw_detections(frame, detections, show_summary=True)
        return annotated, detections
