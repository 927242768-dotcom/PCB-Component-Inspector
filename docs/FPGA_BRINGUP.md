# PG2L100H + RK3568 上板验收步骤

本项目板端固定使用紫光同创 `PG2L100H-6-FBG484`、RK3568 和 PDS `2022.2-SP6.4`。不再按 Vivado/UIO/VDMA 路线描述。

## 1. 生成 PDS 本地工程

在 Windows 开发机执行：

```powershell
cd D:\PCB-Component-Inspector
python scripts\prepare_pds_100h.py --force
```

生成：

```text
fpga\local_pds\pcie_dma_test_100h\pcie_dma_test.pds
```

该目录包含本机 PANGO PCIe/DMA 工程和本项目 PCB 专用 RTL，但由于厂商源码许可限制已加入 `.gitignore`，不会上传 GitHub。

## 2. PDS 实现

使用 PDS 2022.2-SP6.4 打开生成的 `.pds`，确认器件：

```text
Family  Logos2
Device  PG2L100H
Speed   -6
Package FBG484
```

确认工程中存在：

```text
hdl/pcb_preprocess/pango100h_pcb_register_bank.v
hdl/pcb_preprocess/pango100h_pcb_preprocess_bar0.v
```

并确认 PCIe DMA 的 BAR0 实例已经连接到 `u_pango100h_pcb_preprocess`。

然后执行完整流程：综合、Device Map、Place & Route、Timing Analysis、Generate Bitstream。

## 3. 保存实现证据

PCB 专用工程实现完成后保存：

- `.sbit`
- LUT / REG / DRM 资源利用率
- pclk / pclk_div2 时序结果
- WNS / TNS
- 功耗报告（如需要）

这些才是简历中允许填写的本项目量化数据。

## 4. 热下载后恢复 PCIe

将 `.sbit` 热下载到 PG2L100H 后，在 RK3568 执行：

```bash
cd /home/linaro/PCB-Component-Inspector
sudo sh scripts/board_100h_setup.sh
```

脚本会完成 Endpoint remove、PCI rescan、enable 和 `setpci COMMAND=0006`。

目标 PCI 设备：

```text
0002:21:00.0
```

BAR0：

```text
/sys/bus/pci/devices/0002:21:00.0/resource0
```

## 5. 检查 FPGA 状态签名

```bash
sudo python3 scripts/fpga_ctl.py
```

PCB 专用 FPGA 核的签名必须为：

```text
0x50434250
```

如果仍看到其他签名，说明当前下载的不是 PCB 专用 bitstream。

## 6. 最小图像闭环

默认 FPGA 输入：

```text
112 x 64 Gray8 = 7168 bytes
```

BAR0：

```text
0x000~0x0ff  control/status
0x100~       frame input/output
```

默认预处理：

```text
Gaussian 3x3 -> Sobel 3x3 -> threshold
```

ARM 写灰度帧、触发 start、轮询 done，再从 `0x100` 读取 FPGA 结果。

## 7. 实时检测

```bash
sudo -E sh scripts/run_100h_pcb.sh
```

运行链路：

```text
Camera 1280x720
  ├─ 原始高清帧 -> YOLOv8 -> PCB 元器件分类/定位/计数
  └─ resize 112x64 Gray -> PCIe BAR0 -> PG2L100H -> mask/edge readback
```

## 8. 必做 A/B 测试

至少记录：

| 指标 | FPGA bypass | FPGA preprocess |
| --- | ---: | ---: |
| FPGA 单帧处理时间 |  |  |
| 摄像头实时 FPS |  |  |
| YOLO FPS |  |  |
| ARM CPU 占用 |  |  |
| 端到端延迟 |  |  |
| 元器件计数准确率 |  |  |

没有实测前不要填写性能提升百分比。
