# FPGA 实时图像预处理子系统

本目录是 PCB-Component-Inspector 的可综合 FPGA 数据通路。设计目标不是把完整 YOLO 强行塞进 FPGA，而是采用工程上更合理的异构分工：FPGA 处理确定性、高吞吐的像素级运算，ARM 负责设备控制、视频调度和 YOLO 高层识别。

## 数据通路

```text
Camera/RGB888
     |
     v
AXI4-Stream
     |
     +--> rgb2gray            1 pixel/clock
     |
     +--> sobel3x3_stream     2 line buffers + 3-column window
     |
     +--> threshold_stream    optional binary output
     |
     v
AXI4-Stream -> VDMA/Video DMA -> DDR/V4L2 -> ARM -> YOLO
```

控制面：

```text
ARM/Linux -> UIO/mmap -> AXI4-Lite -> pcb_preprocess_regs
```

## RTL 文件

- `rtl/rgb2gray.v`：RGB888 到 Gray8，定点系数 `77/150/29`，无浮点运算。
- `rtl/sobel3x3_stream.v`：两级行缓存构造 3×3 窗口，计算 `|Gx|+|Gy|` 并饱和到 8 bit。
- `rtl/threshold_stream.v`：可配置 8-bit 阈值二值化。
- `rtl/pcb_preprocess_top.v`：AXI4-Stream 预处理流水线顶层。
- `rtl/pcb_preprocess_regs.v`：AXI4-Lite 控制寄存器组。

## 寄存器表

| Offset | Name | R/W | Description |
| --- | --- | --- | --- |
| `0x00` | CONTROL | R/W | bit0 Sobel enable；bit1 threshold enable |
| `0x04` | THRESHOLD | R/W | `[7:0]` threshold |
| `0x08` | WIDTH | R | 编译时图像宽度 |
| `0x0C` | VERSION | R | 核版本，当前 `0x0002_0000` |

## 典型 Vivado 连接

对于 Zynq/ZynqMP 一类 SoC FPGA：

```text
Camera RX / AXIS Source
        -> pcb_preprocess_top
        -> AXI VDMA / Video Frame Buffer Write
        -> DDR
        -> Linux V4L2 / userspace

PS M_AXI_GP/HPM
        -> AXI Interconnect
        -> pcb_preprocess_regs
```

对于“独立 ARM 主机 + PCIe FPGA”结构，可将 `pcb_preprocess_regs` 接入 PCIe BAR，对应 ARM 侧仍可通过 UIO/mmap 使用相同的软件寄存器接口；数据面替换为 PCIe DMA 即可。

## 当前边界

仓库已包含 RTL、寄存器协议、ARM 控制代码和软件测试。由于具体 FPGA 型号、摄像头接口、时钟、DDR/PCIe 拓扑会随开发板变化，XDC、Vivado Block Design、设备树地址和资源利用率必须在确定目标板后生成并实测，不能在未上板时伪造。
