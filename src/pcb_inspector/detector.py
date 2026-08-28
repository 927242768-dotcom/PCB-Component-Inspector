from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import numpy as np
from ultralytics import YOLO


@dataclass(frozen=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_dict(self) -> dict:
        data = asdict(self)
        data.update(width=self.width, height=self.height, area=self.area)
        return data


def _iou(a: Detection, b: Detection) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    iw = max(0.0, x2 - x1)
    ih = max(0.0, y2 - y1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def class_aware_nms(detections: Iterable[Detection], iou_threshold: float = 0.45) -> list[Detection]:
    """对切片重叠区域的重复框做按类别 NMS。"""
    groups: dict[int, list[Detection]] = {}
    for det in detections:
        groups.setdefault(det.class_id, []).append(det)

    kept: list[Detection] = []
    for group in groups.values():
        pending = sorted(group, key=lambda d: d.confidence, reverse=True)
        while pending:
            best = pending.pop(0)
            kept.append(best)
            pending = [candidate for candidate in pending if _iou(best, candidate) < iou_threshold]
    return sorted(kept, key=lambda d: d.confidence, reverse=True)


def _tile_origins(length: int, tile_size: int, overlap: float) -> list[int]:
    if tile_size >= length:
        return [0]
    stride = max(1, int(tile_size * (1.0 - overlap)))
    origins = list(range(0, max(1, length - tile_size + 1), stride))
    last = max(0, length - tile_size)
    if not origins or origins[-1] != last:
        origins.append(last)
    return origins


class ComponentDetector:
    """Ultralytics YOLO PCB 元器件检测器，支持整图和高分辨率切片推理。"""

    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        self.model = YOLO(str(self.model_path))
        self.names = self.model.names

    def _predict_one(self, image: np.ndarray, conf: float, iou: float, imgsz: int) -> list[Detection]:
        result = self.model.predict(
            source=image,
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            verbose=False,
        )[0]
        output: list[Detection] = []
        if result.boxes is None:
            return output

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            score = float(box.conf[0].item())
            x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
            class_name = str(self.names[class_id])
            output.append(
                Detection(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=score,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return output

    def predict(
        self,
        image: np.ndarray,
        *,
        conf: float = 0.25,
        iou: float = 0.45,
        imgsz: int = 1280,
        tile_size: int | None = None,
        tile_overlap: float = 0.20,
    ) -> list[Detection]:
        """检测一张 BGR/RGB numpy 图像。

        tile_size=None 时整图推理；设置 tile_size 后会切片检测并在全图坐标执行 NMS，
        更适合 PCB 上密集的小电阻/电容等目标。
        """
        if image is None or image.size == 0:
            raise ValueError("输入图像为空")

        h, w = image.shape[:2]
        if not tile_size or tile_size <= 0 or (tile_size >= w and tile_size >= h):
            return self._predict_one(image, conf=conf, iou=iou, imgsz=imgsz)

        tile_size = int(tile_size)
        all_detections: list[Detection] = []
        for y0 in _tile_origins(h, tile_size, tile_overlap):
            for x0 in _tile_origins(w, tile_size, tile_overlap):
                x1 = min(w, x0 + tile_size)
                y1 = min(h, y0 + tile_size)
                crop = image[y0:y1, x0:x1]
                local = self._predict_one(crop, conf=conf, iou=iou, imgsz=min(imgsz, max(crop.shape[:2])))
                for det in local:
                    all_detections.append(
                        Detection(
                            class_id=det.class_id,
                            class_name=det.class_name,
                            confidence=det.confidence,
                            x1=det.x1 + x0,
                            y1=det.y1 + y0,
                            x2=det.x2 + x0,
                            y2=det.y2 + y0,
                        )
                    )
        return class_aware_nms(all_detections, iou_threshold=iou)
