# PG2L100H + RK3568 板级实现

本目录对应项目的实际 FPGA 目标平台：

- FPGA：紫光同创 `PG2L100H-6-FBG484`
- ARM：RK3568
- FPGA 工具：PDS `2022.2-SP6.4`
- ARM/FPGA 互联：PCIe Endpoint
- Linux 设备：`0002:21:00.0`
- 数据窗口：`/sys/bus/pci/devices/0002:21:00.0/resource0`
- BAR0：64 KB
- 当前安全 FPGA 灰度输入：`112 x 64`

## 数据链路

```text
USB Camera 1280x720
        |
        v
RK3568 / OpenCV
        |
        +--> 原始高清帧 ---------------------------> YOLOv8 元器件识别/计数
        |
        +--> resize + Gray 112x64
                    |
                    v
             PCIe BAR0 0x100
                    |
                    v
               PG2L100H
          Gaussian -> Sobel -> Threshold
                    |
                    v
             PCIe BAR0 readback
                    |
                    v
            FPGA edge/mask overlay
```

FPGA 负责确定性的像素级预处理，ARM 负责摄像头、参数计算、YOLO 推理、统计与显示。

## BAR0 寄存器

ARM 使用**字节偏移**访问；FPGA 内部 BAR 接口为 128-bit，因此每个寄存器占一个 16-byte word。

| ARM byte offset | FPGA word addr | 功能 |
| --- | --- | --- |
| `0x000` | `0` | CONTROL：bit0 start，bit1 continuous，bit2 clear |
| `0x010` | `1` | WIDTH |
| `0x020` | `2` | HEIGHT |
| `0x030` | `3` | THRESHOLD |
| `0x040` | `4` | ROI_XY |
| `0x050` | `5` | ROI_WH |
| `0x060` | `6` | PREPROCESS_CFG |
| `0x070` | `7` | FRAME_BYTES |
| `0x100` | `16` | 灰度输入/处理结果共享窗口 |

`PREPROCESS_CFG`：

- bit0：invert
- bit1：passthrough
- bit2：Sobel
- bit3：binary threshold
- bit4：Gaussian 3x3

状态签名为 `0x50434250`。

## PDS 本地工程

厂商 PCIe IP/DMA 示例源码带 PANGO 许可证限制，不提交到公开 GitHub。仓库提供自动生成器，从本机已有的官方 100H PCIe 示例生成本地工程：

```powershell
cd D:\PCB-Component-Inspector
python scripts\prepare_pds_100h.py --force
```

生成位置：

```text
fpga/local_pds/pcie_dma_test_100h/pcie_dma_test.pds
```

这个目录已被 `.gitignore` 忽略，只在本机使用。

PDS 中目标器件应为：

```text
Family: Logos2
Device: PG2L100H
Speed:  -6
Package: FBG484
```

板级约束见 `fdc/pcie_dma_test.fdc`。
