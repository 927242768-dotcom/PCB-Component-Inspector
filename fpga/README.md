# FPGA 实时图像预处理子系统

本项目的实际板端目标是 **紫光同创 PG2L100H-6-FBG484 + RK3568**，FPGA 工程使用 **PDS 2022.2-SP6.4**。PG2L100H 作为 PCIe Endpoint，RK3568 Linux 通过 BAR0 `resource0` 与 FPGA 交换控制寄存器和图像数据。

## 实机数据通路

```text
RK3568 Camera 1280x720
        |
        +--> 高分辨率原图 -> YOLOv8
        |
        +--> resize / Gray 112x64
                    |
                    v
        PCIe resource0 / BAR0
                    |
                    v
              PG2L100H
        Gaussian -> Sobel -> Threshold
                    |
                    v
           BAR0 output readback
```

## PG2L100H 专用 RTL

- `rtl/pango100h_pcb_register_bank.v`：128-bit BAR0 控制寄存器。
- `rtl/pango100h_pcb_preprocess_bar0.v`：PG2L100H PCB 图像预处理顶层，实现 Gray8 帧缓存、Gaussian、Sobel、阈值化、ROI 和状态头。
- `pango100h/fdc/pcie_dma_test.fdc`：PG2L100H-6-FBG484 PCIe 工程时钟与板级约束。
- `pango100h/README.md`：板级接口、BAR0 协议和 PDS 工程说明。

## BAR0

ARM 字节偏移：

| Offset | 功能 |
| --- | --- |
| `0x000` | CONTROL / status |
| `0x010` | WIDTH |
| `0x020` | HEIGHT |
| `0x030` | THRESHOLD |
| `0x040` | ROI_XY |
| `0x050` | ROI_WH |
| `0x060` | PREPROCESS_CFG |
| `0x070` | FRAME_BYTES |
| `0x100` | 输入/输出图像共享窗口 |

当前安全帧区为 7936 bytes，默认使用 `112x64 Gray8 = 7168 bytes`。

状态签名：`0x50434250`。

## PDS 本地工程

PANGO PCIe/DMA 示例中的部分厂商 RTL 不适合重新分发，因此公开仓库只保存本项目自研 RTL、FDC 和工程生成脚本。

在有对应 PANGO 100H PCIe 示例工程的 Windows 开发机执行：

```powershell
python scripts\prepare_pds_100h.py --force
```

会生成本地、已接入 PCB 预处理核的：

```text
fpga/local_pds/pcie_dma_test_100h/pcie_dma_test.pds
```

`fpga/local_pds/` 已加入 Git 忽略。

## 通用 RTL

仓库仍保留早期的通用 AXI4-Stream 模块：

- `rgb2gray.v`
- `sobel3x3_stream.v`
- `threshold_stream.v`
- `pcb_preprocess_top.v`
- `pcb_preprocess_regs.v`

这些用于算法级 RTL 验证和其他平台移植；**PG2L100H 实机主路径以 `pango100h_pcb_*` 为准**。

## 验证

GitHub Actions 使用 Icarus Verilog 编译通用 RTL 和 PG2L100H 专用 BAR0 RTL。PDS 的资源占用、时序和 `.sbit` 必须使用 PCB 专用本地工程实际实现后获得，不能直接复用其他工程报告。
