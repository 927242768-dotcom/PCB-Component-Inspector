from __future__ import annotations

from pcb_inspector.detector import Detection, class_aware_nms
from pcb_inspector.reporting import build_json_report, detections_to_csv, summarize


def sample_detections() -> list[Detection]:
    return [
        Detection(17, "resistor", 0.90, 0, 0, 10, 10),
        Detection(17, "resistor", 0.80, 1, 1, 11, 11),
        Detection(10, "ic", 0.95, 20, 20, 40, 40),
    ]


def test_summary_counts() -> None:
    counts = summarize(sample_detections())
    assert counts == {"resistor": 2, "ic": 1}


def test_class_aware_nms_removes_duplicate_same_class() -> None:
    kept = class_aware_nms(sample_detections(), iou_threshold=0.5)
    assert len(kept) == 2
    assert {item.class_name for item in kept} == {"resistor", "ic"}


def test_exports_contain_expected_fields() -> None:
    detections = sample_detections()
    csv_text = detections_to_csv(detections)
    json_text = build_json_report(detections)
    assert "class_name" in csv_text
    assert "resistor" in csv_text
    assert '"total": 3' in json_text
