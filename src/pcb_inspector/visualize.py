from __future__ import annotations

from collections import Counter

import cv2
import numpy as np

from .detector import Detection


def _color_for_class(class_id: int) -> tuple[int, int, int]:
    # 固定映射，保证同一类别每次显示颜色一致。
    return (
        int((37 * class_id + 80) % 205 + 30),
        int((71 * class_id + 50) % 205 + 30),
        int((113 * class_id + 20) % 205 + 30),
    )


def draw_detections(image: np.ndarray, detections: list[Detection], show_summary: bool = True) -> np.ndarray:
    canvas = image.copy()
    h, w = canvas.shape[:2]
    line = max(1, round(min(h, w) / 500))
    font_scale = max(0.45, min(h, w) / 1400)

    for det in detections:
        color = _color_for_class(det.class_id)
        x1, y1, x2, y2 = map(int, (det.x1, det.y1, det.x2, det.y2))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, line)
        label = f"{det.class_name} {det.confidence:.2f}"
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, line)
        ty = max(th + 4, y1)
        cv2.rectangle(canvas, (x1, ty - th - 6), (min(w - 1, x1 + tw + 6), ty + baseline), color, -1)
        cv2.putText(canvas, label, (x1 + 3, ty - 3), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), line, cv2.LINE_AA)

    if show_summary:
        counts = Counter(d.class_name for d in detections)
        lines = [f"Total: {len(detections)}"] + [f"{name}: {count}" for name, count in counts.most_common(10)]
        panel_w = min(w, max(230, int(w * 0.28)))
        panel_h = min(h, 20 + len(lines) * 28)
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (panel_w, panel_h), (245, 245, 245), -1)
        canvas = cv2.addWeighted(overlay, 0.78, canvas, 0.22, 0)
        for idx, text in enumerate(lines):
            cv2.putText(canvas, text, (10, 25 + idx * 27), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (20, 20, 20), 1, cv2.LINE_AA)

    return canvas
