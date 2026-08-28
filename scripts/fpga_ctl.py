from __future__ import annotations

import argparse

from pcb_inspector.fpga import (
    PANGO100H_DEFAULT_HEIGHT,
    PANGO100H_DEFAULT_WIDTH,
    PANGO100H_RESOURCE_ROOT,
    Pango100HPreprocessClient,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PG2L100H PCB 预处理核 BAR0 控制/验板工具")
    parser.add_argument("--resource-root", default=PANGO100H_RESOURCE_ROOT)
    parser.add_argument("--apply", action="store_true", help="应用后续配置；不加时只读取状态")
    parser.add_argument("--width", type=int, default=PANGO100H_DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=PANGO100H_DEFAULT_HEIGHT)
    parser.add_argument("--threshold", type=int, default=96)
    parser.add_argument("--gaussian", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sobel", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--binary", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--passthrough", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--invert", action=argparse.BooleanOptionalAction, default=False)
    return parser


def print_status(status) -> None:
    print(f"busy={status.busy} done={status.done} error={status.error}")
    print(f"frame={status.width}x{status.height} bytes={status.frame_bytes}")
    print(f"frame_counter={status.frame_counter}")
    print(f"threshold={status.threshold} cfg=0x{status.preprocess_cfg:04x}")
    print(f"active_pixels={status.active_pixels} active_ratio={status.active_ratio:.2%}")
    print(f"frame_capacity={status.frame_capacity} abi=0x{status.abi_version:08x}")


def main() -> int:
    args = build_parser().parse_args()
    with Pango100HPreprocessClient(args.resource_root) as fpga:
        print("[before]")
        print_status(fpga.ensure_signature())

        if args.apply:
            cfg = fpga.build_cfg(
                gaussian=args.gaussian,
                sobel=args.sobel,
                binary=args.binary,
                passthrough=args.passthrough,
                invert=args.invert,
            )
            fpga.configure(
                width=args.width,
                height=args.height,
                threshold=args.threshold,
                preprocess_cfg=cfg,
            )
            print("[after configure]")
            print_status(fpga.status())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
