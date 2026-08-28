from __future__ import annotations

import argparse

from pcb_inspector.fpga import UioRegisterMap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PCB FPGA 预处理核控制工具")
    parser.add_argument("--uio", default="/dev/uio0", help="UIO 设备，默认 /dev/uio0")
    parser.add_argument("--sobel", choices=["on", "off"], help="开启/关闭 Sobel")
    parser.add_argument("--threshold-enable", choices=["on", "off"], help="开启/关闭二值阈值")
    parser.add_argument("--threshold", type=int, default=None, help="阈值 0~255")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    with UioRegisterMap(args.uio) as regs:
        before = regs.status()
        if args.sobel is not None or args.threshold_enable is not None or args.threshold is not None:
            regs.configure(
                sobel=(args.sobel == "on") if args.sobel is not None else before.sobel_enabled,
                threshold_enable=(args.threshold_enable == "on") if args.threshold_enable is not None else before.threshold_enabled,
                threshold=args.threshold if args.threshold is not None else before.threshold,
            )
        status = regs.status()

    print(f"FPGA core v{status.version_string}")
    print(f"image_width={status.image_width}")
    print(f"sobel={'on' if status.sobel_enabled else 'off'}")
    print(f"threshold_enable={'on' if status.threshold_enabled else 'off'}")
    print(f"threshold={status.threshold}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
