# PG2L100H + RK3568 + PDS 实机说明

## 目标平台

- FPGA：紫光同创 PG2L100H-6-FBG484
- ARM：RK3568
- 工具：PDS 2022.2-SP6.4
- 互联：PCIe Endpoint
- Linux PCI 设备：0002:21:00.0
- BAR0：resource0，64 KB
- 默认 FPGA 图像尺寸：112 x 64 灰度图

## 本地 PDS 工程

公开仓库不重新分发 PANGO 私有 PCIe/DMA RTL。执行：

```powershell
cd D:\PCB-Component-Inspector
python scripts\prepare_pds_100h.py --force
```

默认从本机已有的 100H PCIe 示例工程生成：

```text
D:\PCB-Component-Inspector\fpga\local_pds\pcie_dma_test_100h\pcie_dma_test.pds
```

生成器会复制本机厂商工程、加入 PCB 专用 BAR0 RTL、替换 BAR0 实例、更新 PDS 源文件列表并写入板级 FDC。`fpga/local_pds/` 只供本机使用并被 Git 忽略。

## PDS 配置

打开生成的 `pcie_dma_test.pds`，确认：

```text
Family  = Logos2
Device  = PG2L100H
Speed   = -6
Package = FBG484
```

执行 PDS 完整实现流程并生成 `.sbit`。最终需要保留本工程自己的综合、布局布线、时序和资源报告。

## BAR0 协议

```text
0x000~0x0ff : 控制与状态
0x100~      : 灰度输入 / FPGA 输出共享窗口
```

默认 112x64 灰度帧共 7168 bytes。ARM 写入一帧后启动 FPGA，等待 done，再从同一窗口读回 Gaussian + Sobel + threshold 的输出。

PCB bitstream 状态签名：

```text
0x50434250
```

## ARM 侧程序

板端 PCIe 重新枚举使用：

```text
scripts/board_100h_setup.sh
```

BAR0 验板：

```text
scripts/fpga_ctl.py
```

实时主程序：

```text
scripts/arm_fpga_realtime.py
scripts/run_100h_pcb.sh
```

实时链路为：摄像头高清帧同时进入两条路径，一路缩成 112x64 灰度帧送 PG2L100H 做低层图像预处理，另一路保留高清图像由 RK3568 侧 YOLO 完成 PCB 元器件分类、定位和计数。

## 同平台已上板实现基线

同一套 PG2L100H + RK3568 + PCIe 100H 平台已有完整 PDS 上板结果，可作为 PCB 工程的板级基线：

| 项目 | 已验证平台基线 |
| --- | ---: |
| PDS | 2022.2-SP6.4 |
| pclk | 250 MHz |
| pclk_div2 | 125 MHz |
| pclk WNS | +0.558 ns |
| pclk_div2 WNS | +0.492 ns |
| LUT 使用率 | 约 15.2% |
| REG 使用率 | 约 3.7% |
| DRM 使用率 | 约 44.8% |
| 时序结论 | All Constraints Met |

这些结果证明该 PG2L100H + RK3568 + PCIe 板级架构和时钟方案已经完成上板验证。PCB 专用核沿用同一平台骨架；若后续需要把“PCB 核本身”的资源增量、单帧耗时或端到端 FPS作为独立性能数字，应再用 PCB 专用 bitstream 的报告替换对应项。
