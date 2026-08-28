from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(r"D:\100H\fpga_work\fpga_demo_100h\pcie_dma_test_100h")
DEFAULT_DEST = ROOT / "fpga" / "local_pds" / "pcie_dma_test_100h"

INSTANCE = """pango100h_pcb_preprocess_bar0 #(
    .ADDR_WIDTH         (ADDR_WIDTH                 )
) u_pango100h_pcb_preprocess (
    .clk                (clk                        ),
    .rst_n              (rst_n                      ),
    .i_bar0_wr_en       (bar0_wr_en                 ),
    .i_bar0_wr_addr     (bar0_wr_addr               ),
    .i_bar0_wr_data     (bar0_wr_data               ),
    .i_bar0_wr_be       (bar0_wr_byte_en            ),
    .i_bar0_rd_clk_en   (i_bar0_rd_clk_en           ),
    .i_bar0_rd_addr     (i_bar0_rd_addr             ),
    .o_bar0_rd_data     (o_bar0_rd_data             )
);"""


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="从已安装/已有的 100H PDS PCIe 示例生成 PCB 专用本地工程")
    p.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    p.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    p.add_argument("--force", action="store_true", help="删除并重建目标目录")
    p.add_argument("--check-only", action="store_true", help="只检查源工程和必要文件")
    return p


def validate_source(source: Path) -> None:
    required = [
        source / "pcie_dma_test.pds",
        source / "hdl" / "pcie_dma_test.v",
        source / "hdl" / "pcie_dma_ctrl" / "ips2l_pcie_dma_rx_top.v",
        source / "ipcore" / "pcie_test" / "pcie_test.idf",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise SystemExit("PDS 源工程缺少文件:\n" + "\n".join(str(x) for x in missing))


def copy_vendor_project(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for dirname in ("hdl", "ipcore"):
        shutil.copytree(source / dirname, dest / dirname, dirs_exist_ok=True)
    for filename in ("pcie_dma_test.pds", "impl.tcl"):
        src = source / filename
        if src.exists():
            shutil.copy2(src, dest / filename)


def patch_rx_top(dest: Path) -> None:
    path = dest / "hdl" / "pcie_dma_ctrl" / "ips2l_pcie_dma_rx_top.v"
    text = path.read_text(encoding="utf-8", errors="ignore")

    old_custom = re.compile(
        r"rk3568_traffic_preprocess_fpga_v2\s*#\(.*?\)\s*"
        r"u_rk3568_traffic_preprocess_fpga\s*\(.*?\);",
        re.S,
    )
    if old_custom.search(text):
        text = old_custom.sub(INSTANCE, text, count=1)
    else:
        # 兼容未改过的 PANGO PCIe DMA demo：替换 BAR0 RAM 实例。
        old_bar0 = re.compile(
            r"ips2l_pcie_dma_ram\s+ips2l_pcie_dma_bar0\s*\(.*?\);",
            re.S,
        )
        if not old_bar0.search(text):
            raise SystemExit("无法在 ips2l_pcie_dma_rx_top.v 中定位 BAR0 RAM/旧预处理实例")
        text = old_bar0.sub(INSTANCE, text, count=1)

    # 某些本机 PCIe 示例曾在 rx_top.v 末尾追加过应用层自定义模块。
    # 生成 PCB 工程时只保留 vendor 的 ips2l_pcie_dma_rx_top 本体，
    # 当前 PCB 逻辑始终由 hdl/pcb_preprocess/ 下的独立文件提供。
    first_endmodule = text.find("endmodule")
    if first_endmodule < 0:
        raise SystemExit("ips2l_pcie_dma_rx_top.v 缺少 endmodule")
    text = text[: first_endmodule + len("endmodule")] + "\n"

    path.write_text(text, encoding="utf-8")


def patch_pds(dest: Path) -> None:
    path = dest / "pcie_dma_test.pds"
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    output: list[str] = []
    inserted = False

    for line in lines:
        if "rk3568_traffic_preprocess_fpga_v2.v" in line:
            indent = line[: len(line) - len(line.lstrip())]
            output.extend(
                [
                    f'{indent}(_file "hdl/pcb_preprocess/pango100h_pcb_register_bank.v"',
                    f'{indent}    (_format verilog)',
                    f'{indent})',
                ]
            )
            output.append(f'{indent}(_file "hdl/pcb_preprocess/pango100h_pcb_preprocess_bar0.v"')
            inserted = True
            continue
        output.append(line)

    if not inserted:
        marker = '(_file "hdl/pcie_dma_ctrl/ips2l_pcie_dma_rx_top.v"'
        new_output: list[str] = []
        for line in output:
            if marker in line and not inserted:
                indent = line[: len(line) - len(line.lstrip())]
                new_output.extend(
                    [
                        f'{indent}(_file "hdl/pcb_preprocess/pango100h_pcb_register_bank.v"',
                        f'{indent}    (_format verilog)',
                        f'{indent})',
                        f'{indent}(_file "hdl/pcb_preprocess/pango100h_pcb_preprocess_bar0.v"',
                        f'{indent}    (_format verilog)',
                        f'{indent})',
                    ]
                )
                inserted = True
            new_output.append(line)
        output = new_output

    if not inserted:
        raise SystemExit("无法在 .pds 中插入 PCB 预处理 RTL")

    path.write_text("\n".join(output) + "\n", encoding="utf-8")


def install_project_rtl(dest: Path) -> None:
    target = dest / "hdl" / "pcb_preprocess"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("pango100h_pcb_register_bank.v", "pango100h_pcb_preprocess_bar0.v"):
        shutil.copy2(ROOT / "fpga" / "rtl" / name, target / name)

    fdc_src = ROOT / "fpga" / "pango100h" / "fdc" / "pcie_dma_test.fdc"
    fdc_dst = dest / "fdc" / "pcie_dma_test.fdc"
    fdc_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fdc_src, fdc_dst)


def main() -> int:
    args = parser().parse_args()
    source = args.source.resolve()
    dest = args.dest.resolve()
    validate_source(source)
    print(f"PDS source OK: {source}")

    if args.check_only:
        return 0

    if dest.exists() and args.force:
        shutil.rmtree(dest)
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"目标目录非空：{dest}，需要重建请加 --force")

    copy_vendor_project(source, dest)
    install_project_rtl(dest)
    patch_rx_top(dest)
    patch_pds(dest)

    print(f"已生成本地 PDS 工程：{dest / 'pcie_dma_test.pds'}")
    print("器件：PG2L100H-6-FBG484；建议 PDS：2022.2-SP6.4")
    print("下一步：用 PDS 打开 pcie_dma_test.pds，执行全流程并生成 .sbit。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
