from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from pcb_inspector.detector import ComponentDetector
from pcb_inspector.fpga import UioRegisterMap
from pcb_inspector.model_registry import ensure_default_model
from pcb_inspector.visualize import draw_detections


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ARM + FPGA + YOLO 实时 PCB 元器件检测演示")
    parser.add_argument("--camera", default="0", help="V4L2 摄像头编号或 /dev/videoX")
    parser.add_argument("--uio", default="/dev/uio0", help="FPGA UIO 控制设备")
    parser.add_argument("--model", help="YOLO 权重，不填则使用默认模型")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--infer-every", type=int, default=2, help="每 N 帧执行一次 YOLO")
    parser.add_argument("--threshold", type=int, default=96)
    parser.add_argument("--sobel", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--binary", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--headless", action="store_true", help="不打开 GUI，仅打印实时 FPS/计数")
    return parser


def _camera_source(value: str):
    return int(value) if value.isdigit() else value


def main() -> int:
    args = build_parser().parse_args()
    if args.infer_every < 1:
        raise SystemExit("--infer-every 必须 >= 1")

    model_path = Path(args.model) if args.model else ensure_default_model()
    detector = ComponentDetector(model_path)

    # 控制面：ARM 通过 UIO/MMIO 配置 FPGA 预处理核。
    with UioRegisterMap(args.uio) as regs:
        regs.configure(sobel=args.sobel, threshold_enable=args.binary, threshold=args.threshold)
        status = regs.status()
        print(
            f"FPGA v{status.version_string}: sobel={status.sobel_enabled}, "
            f"binary={status.threshold_enabled}, threshold={status.threshold}, width={status.image_width}"
        )

    # 数据面：FPGA + Video DMA 输出通过 V4L2 暴露给 ARM，OpenCV 直接取处理后的帧。
    cap = cv2.VideoCapture(_camera_source(args.camera))
    if not cap.isOpened():
        raise SystemExit(f"无法打开视频设备：{args.camera}")

    frame_idx = 0
    latest = []
    tick = time.perf_counter()
    fps_tick = tick
    fps_frames = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_idx += 1
            fps_frames += 1

            if frame_idx == 1 or frame_idx % args.infer_every == 0:
                latest = detector.predict(frame, conf=args.conf, iou=args.iou, imgsz=args.imgsz)

            annotated = draw_detections(frame, latest, show_summary=True)
            now = time.perf_counter()
            if now - fps_tick >= 1.0:
                fps = fps_frames / (now - fps_tick)
                print(f"stream_fps={fps:.1f}, detections={len(latest)}")
                fps_tick = now
                fps_frames = 0

            if not args.headless:
                cv2.imshow("ARM + FPGA PCB Inspector", annotated)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
    finally:
        cap.release()
        if not args.headless:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - tick
    print(f"frames={frame_idx}, elapsed={elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
