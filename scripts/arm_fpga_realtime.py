from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from pcb_inspector.detector import ComponentDetector
from pcb_inspector.fpga import (
    PANGO100H_DEFAULT_HEIGHT,
    PANGO100H_DEFAULT_WIDTH,
    PANGO100H_RESOURCE_ROOT,
    Pango100HPreprocessClient,
)
from pcb_inspector.model_registry import ensure_default_model
from pcb_inspector.visualize import draw_detections


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PG2L100H + RK3568 + YOLO 实时 PCB 元器件检测")
    parser.add_argument("--camera", default="0", help="V4L2 摄像头编号或 /dev/videoX")
    parser.add_argument("--camera-width", type=int, default=1280)
    parser.add_argument("--camera-height", type=int, default=720)
    parser.add_argument("--resource-root", default=PANGO100H_RESOURCE_ROOT)
    parser.add_argument("--model", help="YOLO 权重，不填则使用默认模型")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--infer-every", type=int, default=2, help="每 N 帧执行一次 YOLO")
    parser.add_argument("--fpga-width", type=int, default=PANGO100H_DEFAULT_WIDTH)
    parser.add_argument("--fpga-height", type=int, default=PANGO100H_DEFAULT_HEIGHT)
    parser.add_argument("--threshold-mode", choices=["fixed", "percentile"], default="percentile")
    parser.add_argument("--threshold", type=int, default=96)
    parser.add_argument("--threshold-percentile", type=float, default=78.0)
    parser.add_argument("--gaussian", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sobel", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--binary", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--invert", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--show-mask", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--max-frames", type=int, default=0, help="0 表示持续运行")
    return parser


def _camera_source(value: str):
    return int(value) if value.isdigit() else value


def _threshold_for(gray_small: np.ndarray, args: argparse.Namespace) -> int:
    if args.threshold_mode == "fixed":
        return int(np.clip(args.threshold, 0, 255))
    return int(np.clip(np.percentile(gray_small, args.threshold_percentile), 24, 220))


def _overlay_mask(frame: np.ndarray, mask_small: np.ndarray) -> np.ndarray:
    mask = cv2.resize(mask_small, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST)
    canvas = frame.copy()
    active = mask > 0
    if np.any(active):
        # 不改变真实检测输入，只在显示图上做轻量高亮。
        canvas[active, 1] = np.maximum(canvas[active, 1], 180)
    return canvas


def main() -> int:
    args = build_parser().parse_args()
    if args.infer_every < 1:
        raise SystemExit("--infer-every 必须 >= 1")

    Pango100HPreprocessClient.validate_frame_size(args.fpga_width, args.fpga_height)
    cfg = Pango100HPreprocessClient.build_cfg(
        gaussian=args.gaussian,
        sobel=args.sobel,
        binary=args.binary,
        invert=args.invert,
    )

    model_path = Path(args.model) if args.model else ensure_default_model()
    detector = ComponentDetector(model_path)

    cap = cv2.VideoCapture(_camera_source(args.camera), cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.camera_height)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    if not cap.isOpened():
        raise SystemExit(f"无法打开视频设备：{args.camera}")

    frame_idx = 0
    latest = []
    last_mask = np.zeros((args.fpga_height, args.fpga_width), dtype=np.uint8)
    last_fpga_ms = 0.0
    last_active_ratio = 0.0
    started = time.perf_counter()
    fps_started = started
    fps_frames = 0

    try:
        with Pango100HPreprocessClient(args.resource_root) as fpga:
            initial = fpga.ensure_signature()
            print(
                "PG2L100H ready: "
                f"frame={initial.width}x{initial.height}, "
                f"counter={initial.frame_counter}, capacity={initial.frame_capacity} bytes"
            )

            while True:
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("摄像头读取失败")
                frame_idx += 1
                fps_frames += 1

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray_small = cv2.resize(
                    gray,
                    (args.fpga_width, args.fpga_height),
                    interpolation=cv2.INTER_AREA,
                )
                threshold = _threshold_for(gray_small, args)

                fpga.configure(
                    width=args.fpga_width,
                    height=args.fpga_height,
                    threshold=threshold,
                    preprocess_cfg=cfg,
                )
                fpga_t0 = time.perf_counter()
                last_mask, fpga_status = fpga.process(gray_small)
                last_fpga_ms = (time.perf_counter() - fpga_t0) * 1000.0
                last_active_ratio = fpga_status.active_ratio

                if frame_idx == 1 or frame_idx % args.infer_every == 0:
                    latest = detector.predict(
                        frame,
                        conf=args.conf,
                        iou=args.iou,
                        imgsz=args.imgsz,
                    )

                display_frame = _overlay_mask(frame, last_mask) if args.show_mask else frame
                annotated = draw_detections(display_frame, latest, show_summary=True)
                cv2.putText(
                    annotated,
                    f"FPGA {args.fpga_width}x{args.fpga_height} {last_fpga_ms:.1f}ms active={last_active_ratio:.1%}",
                    (12, annotated.shape[0] - 18),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.58,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

                now = time.perf_counter()
                if now - fps_started >= 1.0:
                    fps = fps_frames / (now - fps_started)
                    print(
                        f"stream_fps={fps:.1f}, fpga_ms={last_fpga_ms:.1f}, "
                        f"active={last_active_ratio:.1%}, detections={len(latest)}"
                    )
                    fps_started = now
                    fps_frames = 0

                if not args.headless:
                    cv2.imshow("PG2L100H + RK3568 PCB Inspector", annotated)
                    if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                        break

                if args.max_frames and frame_idx >= args.max_frames:
                    break
    finally:
        cap.release()
        if not args.headless:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - started
    print(f"frames={frame_idx}, elapsed={elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
