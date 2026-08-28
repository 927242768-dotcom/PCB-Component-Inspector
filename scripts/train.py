from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="训练/微调 PCB 元器件 YOLO 模型")
    parser.add_argument("--data", default="configs/pcb_components.yaml", help="YOLO 数据集 YAML")
    parser.add_argument("--weights", default="yolov8s.pt", help="预训练权重或模型 YAML")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="", help="例如 0 / cpu；留空让 Ultralytics 自动选择")
    parser.add_argument("--name", default="pcb_components_v1")
    args = parser.parse_args()

    if not Path(args.data).exists():
        raise SystemExit(f"找不到数据配置：{args.data}。请先按 docs/DATASET.md 准备数据集。")

    model = YOLO(args.weights)
    train_args = dict(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project="runs/detect",
        name=args.name,
        patience=30,
        optimizer="auto",
        close_mosaic=15,
        degrees=5.0,
        translate=0.08,
        scale=0.35,
        fliplr=0.5,
        mosaic=0.7,
        mixup=0.05,
        copy_paste=0.0,
        seed=42,
    )
    if args.device:
        train_args["device"] = args.device
    model.train(**train_args)


if __name__ == "__main__":
    main()
