from __future__ import annotations

import numpy as np
import pytest

from pcb_inspector.detector import Detection
from pcb_inspector.video import FrameDetectionPipeline, FrameInferenceSettings


class FakeDetector:
    def __init__(self, *, return_empty: bool = False) -> None:
        self.calls = 0
        self.return_empty = return_empty

    def predict(self, image, **kwargs):
        self.calls += 1
        if self.return_empty:
            return []
        return [Detection(17, "resistor", 0.9, 5, 5, 20, 20)]


def test_video_pipeline_respects_detect_every() -> None:
    detector = FakeDetector()
    pipeline = FrameDetectionPipeline(
        detector,
        FrameInferenceSettings(imgsz=640),
        detect_every=2,
    )
    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    annotated1, detections1 = pipeline.process(frame)
    annotated2, detections2 = pipeline.process(frame)
    annotated3, detections3 = pipeline.process(frame)

    assert detector.calls == 2
    assert annotated1.shape == frame.shape
    assert annotated2.shape == frame.shape
    assert annotated3.shape == frame.shape
    assert detections1[0].class_name == "resistor"
    assert detections2[0].class_name == "resistor"
    assert detections3[0].class_name == "resistor"


def test_video_pipeline_does_not_reinfer_every_frame_when_no_detections() -> None:
    detector = FakeDetector(return_empty=True)
    pipeline = FrameDetectionPipeline(
        detector,
        FrameInferenceSettings(imgsz=640),
        detect_every=3,
    )
    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    for _ in range(4):
        pipeline.process(frame)

    assert detector.calls == 2
    assert pipeline.last_detections == []


def test_video_pipeline_rejects_invalid_detect_every() -> None:
    with pytest.raises(ValueError, match="detect_every"):
        FrameDetectionPipeline(FakeDetector(), FrameInferenceSettings(), detect_every=0)
