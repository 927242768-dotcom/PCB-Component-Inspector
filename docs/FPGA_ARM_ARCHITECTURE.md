# FPGA + ARM 实时 PCB 元器件视觉检测架构

## 1. 项目定位

本项目从纯软件 YOLO 检测升级为 FPGA + ARM 异构视觉系统。设计原则是把不同类型的计算放到最合适的硬件上：

- **FPGA/PL**：摄像头视频流、RGB 转灰度、3×3 Sobel、阈值化、流式像素处理；
- **ARM/PS**：寄存器配置、V4L2/VDMA 视频调度、模型调用、结果管理；
- **YOLO**：元器件类别识别、定位、计数；
- **Web/GUI**：结果可视化和报告导出。

这比“把所有算法都叫 FPGA 加速”更容易上板、验证和在面试中解释。

## 2. 端到端链路

```text
CMOS / USB / MIPI Camera
          |
          v
   Video Receiver
          |
          v
  AXI4-Stream RGB888
          |
          v
+--------------------------+
| FPGA Pixel Pipeline      |
| RGB2Gray                 |
| 3x3 line buffer          |
| Sobel                    |
| Threshold (optional)     |
+--------------------------+
          |
          v
 VDMA / PCIe DMA / DDR
          |
          v
       ARM Linux
          |
    V4L2/OpenCV frame
          |
          v
       YOLOv8
          |
          v
class + bbox + confidence
          |
     count / report / UI
```

## 3. FPGA 微架构

### RGB2Gray

使用定点近似：

`Gray = (77*R + 150*G + 29*B) >> 8`

系数和为 256，可用 DSP 或综合器映射为乘加逻辑。模块遵循 ready/valid 反压，目标吞吐为每周期一个像素。

### 3×3 Sobel

Sobel 需要同时看到当前像素周围 3×3 邻域，因此 RTL 使用：

- 两条行缓存保存前两行；
- 每一行两个横向移位寄存器保存前两列；
- 在连续视频流中滚动构造 3×3 窗口。

核函数：

```text
Gx = [-1 0 1; -2 0 2; -1 0 1]
Gy = [-1 -2 -1; 0 0 0; 1 2 1]
```

硬件中使用 `|Gx| + |Gy|` 近似梯度幅值，避免平方、开方，结果饱和到 8 bit。

### Threshold

阈值寄存器由 ARM 动态配置，输出 0/255 二值结果。可以关闭该模块，只使用 Gray/Sobel 输出。

## 4. ARM 控制面

ARM 通过 Linux UIO 将控制寄存器映射到用户态：

```python
with UioRegisterMap('/dev/uio0') as regs:
    regs.configure(sobel=True, threshold_enable=False, threshold=96)
```

同一寄存器协议也可映射到 PCIe BAR，因此架构不绑定某一种 ARM+FPGA 物理连接方式。

## 5. 为什么 YOLO 目前不放 FPGA

完整 YOLOv8 FPGA 部署涉及量化、算子支持、片上存储、DDR 带宽、卷积阵列和模型编译链。若在没有对应板卡资源和量化精度数据时直接声称“YOLO 已由 FPGA 加速”，很容易在面试中被追问穿。

当前版本把 FPGA 放在**真正已经实现且适合 RTL 的实时视频预处理**上；后续可继续做 INT8 量化，并把卷积/激活等热点算子迁移到 FPGA/NPU。

## 6. 可量化指标

上板后必须记录：

- FPGA 时钟频率；
- 输入分辨率和视频帧率；
- LUT / FF / BRAM / DSP 占用；
- RTL 流水线端到端延迟；
- ARM-only 与 FPGA-preprocess 两种模式 CPU 占用；
- YOLO 推理 FPS；
- 元器件计数准确率和 mAP。

这些数据将成为简历里最有价值的定量结果。
