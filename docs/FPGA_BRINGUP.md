# FPGA + ARM 上板验收步骤

本文件用于把仓库中的 RTL/ARM 代码真正闭环到开发板。未完成某项实测前，不应把对应指标写进简历。

## 1. Vivado/Quartus 侧

1. 确认目标 FPGA 型号、视频输入接口和像素时钟。
2. 将 `fpga/rtl/` 加入工程。
3. 以 `pcb_preprocess_top` 作为视频数据面 IP 核。
4. 以 `pcb_preprocess_regs` 作为控制面寄存器核。
5. 将视频源 AXI4-Stream 接到预处理核，再接 VDMA/Frame Buffer/PCIe DMA。
6. 将 AXI-Lite 控制口连接 PS 总线或 PCIe BAR。
7. 设置 `IMAGE_WIDTH` 为真实输入宽度。
8. 完成综合、实现、时序收敛并导出 bitstream。
9. 保存 utilization 和 timing summary，作为简历数据来源。

## 2. Linux/ARM 侧

确认 UIO：

```bash
ls -l /dev/uio*
cat /sys/class/uio/uio0/name
```

检查寄存器：

```bash
python scripts/fpga_ctl.py --uio /dev/uio0
```

配置 Sobel：

```bash
python scripts/fpga_ctl.py --uio /dev/uio0 --sobel on --threshold-enable off
```

配置 Sobel + 二值化：

```bash
python scripts/fpga_ctl.py --uio /dev/uio0 --sobel on --threshold-enable on --threshold 96
```

## 3. 视频链路

确认 V4L2 节点：

```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --all
```

先只验证视频，不跑 YOLO；确认分辨率、帧率、行尾和帧首标记均正确。

随后运行：

```bash
python scripts/arm_fpga_realtime.py \
  --camera /dev/video0 \
  --uio /dev/uio0 \
  --imgsz 640 \
  --infer-every 2
```

## 4. 必做 A/B 对比

至少测试两组：

- A：FPGA Sobel/threshold bypass，只走原始视频；
- B：启用 FPGA 预处理。

记录：

| 指标 | ARM-only / bypass | FPGA preprocess |
| --- | ---: | ---: |
| 输入 FPS |  |  |
| YOLO FPS |  |  |
| ARM CPU 占用 |  |  |
| 端到端延迟 |  |  |
| 计数准确率 |  |  |

## 5. 简历允许写的条件

只有完成真实板卡验证后，才把“实现 FPGA 实时预处理并达到 XX FPS / 降低 XX% CPU 占用”等定量表述写入简历。当前仓库已经具备 RTL 和软件闭环代码，但资源利用率、时钟频率、功耗和真实帧率必须来自目标板实际报告。
