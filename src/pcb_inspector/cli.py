from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from .detector import ComponentDetector
from .model_registry import ensure_default_model
from .reporting import build_json_report, detections_to_csv, summarize
from .visualize import draw_detections


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PCB 元器件识别与统计")
    parser.add_argument("source", help="待识别 PCB 图片路径")
    parser.add_argument("--model", help="YOLO 权重路径；不填则自动下载默认开源模型")
    parser.add_argument("--output", default="outputs", help="输出目录")
    parser.add_argument("--conf", type=float, default=0.25, help="置信度阈值")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IoU 阈值")
    parser.add_argument("--imgsz", type=int, default=1280, help="模型输入尺寸")
    parser.add_argument("--tile", type=int, default=0, help="切片尺寸，0 表示关闭；小元器件建议 1024~1280")
    parser.add_argument("--overlap", type=float, default=0.20, help="切片重叠比例")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = Path(args.source)
    if not source.exists():
        raise SystemExit(f"找不到图片：{source}")

    model_path = Path(args.model) if args.model else ensure_default_model()
    image = cv2.imread(str(source))
    if image is None:
        raise SystemExit(f"无法读取图片：{source}")

    detector = ComponentDetector(model_path)
    detections = detector.predict(
        image,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        tile_size=args.tile or None,
        tile_overlap=args.overlap,
    )

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    annotated = draw_detections(image, detections)
    stem = source.stem
    cv2.imwrite(str(out_dir / f"{stem}_annotated.jpg"), annotated)
    (out_dir / f"{stem}_detections.csv").write_text(detections_to_csv(detections), encoding="utf-8-sig")
    (out_dir / f"{stem}_report.json").write_text(build_json_report(detections), encoding="utf-8")

    print(f"识别完成：共 {len(detections)} 个元器件")
    for name, count in summarize(detections).items():
        print(f"  {name}: {count}")
    print(f"结果目录：{out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
