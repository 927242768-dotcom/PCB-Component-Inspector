from __future__ import annotations

import csv
import io
import json
from collections import Counter
from typing import Iterable

from .detector import Detection


def summarize(detections: Iterable[Detection]) -> dict[str, int]:
    counts = Counter(det.class_name for det in detections)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].lower())))


def detections_to_csv(detections: Iterable[Detection]) -> str:
    buffer = io.StringIO()
    fieldnames = ["class_id", "class_name", "confidence", "x1", "y1", "x2", "y2", "width", "height", "area"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for det in detections:
        row = det.to_dict()
        row["confidence"] = round(row["confidence"], 6)
        for key in ("x1", "y1", "x2", "y2", "width", "height", "area"):
            row[key] = round(row[key], 2)
        writer.writerow(row)
    return buffer.getvalue()


def build_json_report(detections: Iterable[Detection]) -> str:
    detections = list(detections)
    payload = {
        "total": len(detections),
        "counts": summarize(detections),
        "detections": [det.to_dict() for det in detections],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
