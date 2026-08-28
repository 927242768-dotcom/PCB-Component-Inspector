# FPGA 简历项目表述

## 项目名称

**基于 PG2L100H + RK3568 的实时 PCB 元器件视觉检测系统**

## 当前可直接写进简历的内容

- 基于紫光同创 **PG2L100H-6-FBG484** 与 RK3568 搭建 ARM+FPGA 异构视觉系统，使用 PDS 2022.2-SP6.4 完成 FPGA 工程组织，ARM/FPGA 通过 PCIe Endpoint 通信。
- 在 FPGA 侧设计面向 PCB 图像的低层预处理数据通路，实现 **3x3 Gaussian、Sobel 边缘提取和动态阈值化**；以 128-bit BAR0 数据字组织灰度帧，通过三行窗口和跨 16-byte word 像素访问完成 3x3 邻域运算。
- 设计 **64 KB 单 BAR0 共享窗口协议**，控制/状态位于 0x000~0x0ff，图像输入/输出位于 0x100 起始区域；RK3568 Linux 通过 `/sys/bus/pci/devices/0002:21:00.0/resource0` + mmap 完成寄存器配置、图像写入和结果读取。
- ARM 侧将 1280x720 摄像头画面缩放为 **112x64 灰度帧**送入 FPGA 进行预处理，同时保留高清帧用于 YOLOv8 PCB 元器件识别、分类和自动计数，实现低层图像硬件处理与高层 AI 推理分工。
- 实现 PCIe 热下载后的 Endpoint 重枚举、BAR0 状态签名检查、FPGA 参数动态配置、实时摄像头检测，以及图片/视频/摄像头三种软件检测模式。
- 建立 Python 单元测试、Icarus Verilog RTL 编译检查、GitHub Actions CI 和 Release 流程。

## 30 秒面试讲法

“这个项目使用紫光同创 PG2L100H 和 RK3568。摄像头原始画面在 ARM 侧采集，其中一路保留高清图给 YOLO 做 PCB 元器件分类和计数，另一路缩成 112x64 灰度图，通过 PCIe BAR0 写到 FPGA。FPGA 用 3x3 Gaussian、Sobel 和阈值化做确定性的像素级预处理，处理结果再通过同一个 BAR0 窗口读回。ARM Linux 直接 mmap PCIe resource0 完成寄存器和帧数据交换。FPGA 工程使用紫光 PDS，而不是 Vivado。”

## 已验证硬件平台基线

本项目复用同一套 PG2L100H + RK3568 + PCIe 硬件平台。该 100H 平台已经完成 PDS 上板验证，可作为当前 PCB 工程的板级实现基线：

- PDS：`2022.2-SP6.4`
- FPGA：`PG2L100H-6-FBG484`
- PCIe 用户时钟：`pclk = 250 MHz`、`pclk_div2 = 125 MHz`
- 时序结果：250 MHz `pclk` WNS `+0.558 ns`；125 MHz `pclk_div2` WNS `+0.492 ns`
- 资源占用基线：LUT 约 `15.2%`、寄存器约 `3.7%`、DRM 约 `44.8%`
- 实现结论：`All Constraints Met`

这些数字是**同一 PG2L100H/PCIe 平台的已上板实现基线**，可用于说明板级架构、时钟和资源余量；PCB 专用预处理核自身的增量资源、单帧耗时和端到端 FPS 后续应以该 PCB bitstream 的独立实现报告替换。

### 简历推荐量化写法

> 基于紫光同创 PG2L100H-6-FBG484 与 RK3568 搭建 PCIe 异构视觉平台，PDS 实现基线达到 250 MHz/125 MHz 用户时钟，WNS 分别为 +0.558 ns/+0.492 ns，LUT/REG/DRM 占用约 15.2%/3.7%/44.8%，时序约束全部满足；在该平台上实现 PCB 图像 Gaussian、Sobel、动态阈值预处理，并由 RK3568 完成 YOLOv8 元器件识别与计数。

## 高频追问

### 为什么 FPGA 输入只有 112x64？

当前采用 100H 已验证稳定的单 BAR0 小帧闭环，112x64 灰度帧只有 7168 bytes，适合快速完成 PCIe 写入、FPGA 处理和读回。YOLO 仍然使用高清原始帧，因此不会因为 FPGA 低分辨率输入直接丢失元器件识别细节。

### 为什么不用 FPGA 跑完整 YOLO？

完整 YOLO FPGA 化需要 INT8 量化、卷积阵列、片上缓存和外部存储带宽设计。当前项目把适合 RTL 的 Gaussian/Sobel/threshold 放在 FPGA，把类别语义识别放在 ARM 侧 YOLO，软硬件边界清晰，也更容易真实验证。

### ARM 和 FPGA 怎么通信？

PG2L100H 作为 PCIe Endpoint，RK3568 Linux 枚举为 `0002:21:00.0`。用户态程序 mmap `resource0`，通过 BAR0 写控制寄存器和灰度帧，再轮询状态并读回 FPGA 输出。

### Sobel 的 3x3 窗口怎么做？

FPGA 每次处理 128-bit，也就是 16 个灰度像素。每一行按 16-byte word 存储，处理当前 word 时同时取左/中/右三个 word，并使用上一行、当前行、下一行组成 3x3 邻域；跨 word 的左右像素通过索引映射读取。

### 为什么 Sobel 不开平方？

梯度幅值使用 `|Gx|+|Gy|`，避免平方和开方电路，降低组合逻辑和流水线复杂度，适合 FPGA 定点实现。
