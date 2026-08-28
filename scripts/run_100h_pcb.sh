#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/linaro/.Xauthority}"

python3 scripts/arm_fpga_realtime.py \
  --resource-root /sys/bus/pci/devices/0002:21:00.0 \
  --camera 0 \
  --camera-width 1280 \
  --camera-height 720 \
  --fpga-width 112 \
  --fpga-height 64 \
  --threshold-mode percentile \
  --threshold-percentile 78 \
  --gaussian \
  --sobel \
  --binary \
  --show-mask \
  --imgsz 640 \
  --infer-every 2
