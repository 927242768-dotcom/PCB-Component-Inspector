# PG2L100H + RK3568 实时 PCB 元器件视觉检测架构

## 1. 实际硬件平台

- FPGA：紫光同创 PG2L100H-6-FBG484
- ARM：RK3568
- FPGA 工具：PDS 2022.2-SP6.4
- ARM/FPGA：PCIe Endpoint
- Linux 设备：0002:21:00.0
- BAR0：64 KB resource0
- FPGA 当前安全图像尺寸：112x64 Gray8

项目保留 PC/Streamlit 图片和视频模式用于算法验证；真正的板端模式使用 RK3568 + PG2L100H。

## 2. 端到端链路

```text
USB Camera 1280x720 MJPG
          |
          v
      RK3568 V4L2
          |
          +------------------------------+
          |                              |
          v                              v
 resize + Gray 112x64              原始高清 BGR
          |                              |
          v                              v
 PCIe BAR0 resource0                    YOLOv8
          |                              |
          v                              v
       PG2L100H                  component bbox/class/count
 Gaussian 3x3                           |
 Sobel 3x3                              |
 Threshold                              |
          |                              |
          +---- BAR0 readback -----------+
                         |
                         v
                 overlay / report / UI
```

## 3. PCIe BAR0 数据协议

PCIe DMA 示例工程内部 BAR0 数据宽度为 128 bit。ARM 侧使用 sysfs resource0 的**字节偏移**访问，FPGA 侧使用 16-byte word 地址。

```text
ARM offset   FPGA word   Function
0x000        0           CONTROL / status word0
0x010        1           WIDTH
0x020        2           HEIGHT
0x030        3           THRESHOLD
0x040        4           ROI_XY
0x050        5           ROI_WH
0x060        6           PREPROCESS_CFG
0x070        7           FRAME_BYTES
0x100        16          frame payload begins
```

状态签名：`0x50434250`。

## 4. FPGA 微架构

### 128-bit 图像存储

一拍 BAR0 数据包含 16 个 Gray8 像素。112 像素宽度正好是 7 个 128-bit word，因此每行按 7 word 存储。

### Gaussian

核：

```text
1 2 1
2 4 2   /16
1 2 1
```

乘 2、乘 4 和除 16 可以由移位实现。

### Sobel

```text
Gx = [-1 0 1; -2 0 2; -1 0 1]
Gy = [-1 -2 -1; 0 0 0; 1 2 1]
```

梯度幅值使用 `|Gx| + |Gy|` 并饱和到 8 bit。

### 3x3 邻域

处理某一 128-bit word 时，FPGA 同时维护上一行、当前行、下一行，并读取左/中/右三个 word。`triplet_byte` 负责处理 16-byte word 边界，因此第 0/15 个像素也能访问相邻 word 的像素。

### Threshold

ARM 可以按固定阈值或当前图像 percentile 动态计算阈值，再写入 BAR0。输出可配置为灰度、Sobel 强度或 0/255 二值结果。

## 5. ARM 软件

`Pango100HPreprocessClient` 直接打开：

```text
/sys/bus/pci/devices/0002:21:00.0/resource0
```

然后 mmap 64 KB BAR0，完成：

1. 配置宽高/阈值/预处理模式；
2. 写 112x64 灰度帧；
3. 写 CONTROL.start；
4. 轮询 busy/done/error；
5. 从 0x100 读回 FPGA 输出。

实时入口为 `scripts/arm_fpga_realtime.py`。

## 6. 为什么 YOLO 保留在 ARM 侧

PG2L100H 当前承担低层、规则、吞吐稳定的像素运算；YOLO 涉及大量卷积、量化、权重存储和算子适配，因此先放在 ARM/CPU/NPU 侧更合理。该划分能真实体现 FPGA 数据通路设计、PCIe 联调和软硬件协同，而不虚构“全 YOLO FPGA 加速”。

## 7. 工程与验证

- 自研 RTL：`fpga/rtl/pango100h_pcb_*.v`
- 板级 FDC：`fpga/pango100h/fdc/pcie_dma_test.fdc`
- 本地 PDS 生成器：`scripts/prepare_pds_100h.py`
- ARM BAR0 控制：`src/pcb_inspector/fpga.py`
- 板端实时程序：`scripts/arm_fpga_realtime.py`
- GitHub CI：Python 单测 + Icarus Verilog RTL 编译

PDS 资源利用率、WNS、Fmax 和板端 FPS 必须使用 PCB 专用工程重新实现后的真实报告。
