# 系统架构

## 1. 项目目标

PCB-Component-Inspector 用于从 PCB 图像中检测板载元器件，输出每个目标的类别、位置与置信度，并进一步完成自动计数、可视化标注和结构化报告导出。

系统重点处理 PCB 场景中常见的三个问题：

- 元器件尺寸小；
- 同一张图中目标数量多且密集；
- 高分辨率整图直接缩放后容易丢失细节。

## 2. 模块划分

### `model_registry.py`

负责默认模型的获取与本地路径管理。模型文件不提交到 Git 仓库，首次使用时从公开模型源下载。

### `detector.py`

负责核心检测流程，包括：

- Ultralytics 模型加载；
- 整图推理；
- 高分辨率切片；
- 切片坐标还原；
- 跨切片同类别 NMS；
- 检测结果统一为结构化对象。

### `reporting.py`

负责把检测结果转换为：

- 总目标数量；
- 每类别数量；
- CSV 逐目标明细；
- JSON 汇总报告。

### `visualize.py`

负责在原始图像上绘制：

- bbox；
- 类别名称；
- 置信度。

### `video.py`

负责视频与摄像头逐帧检测，包括：

- 统一的视频帧推理参数；
- 线程安全的逐帧处理；
- 每 N 帧执行一次 YOLO 的性能控制；
- 中间帧复用最近一次检测结果；
- 每帧检测框与当前分类计数叠加。

### `cli.py`

提供命令行入口，适合批处理、脚本调用和自动化任务。

### `app.py`

提供 Streamlit 图形界面，支持静态图片、上传视频与 WebRTC 浏览器摄像头实时检测。

## 3. 推理流程

### 整图模式

适合分辨率不高、目标尺寸较大的 PCB 图像：

```text
Image -> YOLO -> Detections -> Count -> Draw -> Export
```

### 切片模式

适合高分辨率、密集小目标场景：

```text
High-resolution image
        |
        v
Overlapping tiles
        |
        v
YOLO per tile
        |
        v
Restore global coordinates
        |
        v
Class-aware global NMS
        |
        v
Final detections
        |
        +--> Count
        +--> Visualization
        +--> CSV / JSON
```

### 视频与实时摄像头模式

```text
Video file / Browser camera
        |
        v
Decode current frame
        |
        v
FrameDetectionPipeline
        |
        +--> YOLO every N frames
        |        |
        |        v
        |   Current detections
        |        |
        +<-------+
        |
        v
Reuse latest detections on skipped frames
        |
        v
Draw boxes + current counts
        |
        +--> WebRTC live return
        +--> Annotated MP4 output
```

实时模式的计数表示当前帧同时检测到的元器件数量，不对连续帧做累加，避免同一器件在视频中被重复计数。

## 4. 切片设计

切片之间保留一定重叠区域，避免元器件刚好落在切片边界时被截断。

默认建议：

- `tile=1024`；
- `overlap=0.20`；
- `imgsz=1280`。

每个切片预测完成后，检测框坐标会转换回原图坐标。由于重叠区域可能对同一个器件产生多个框，随后使用按类别全局 NMS 去重。

## 5. 计数逻辑

系统计数基于最终 NMS 后的检测结果，而不是直接统计所有模型原始输出，因此能够降低切片重叠造成的重复计数。

最终报告至少包含：

- `total`：检测目标总数；
- `counts`：各类别数量；
- `detections`：逐目标类别、置信度和 bbox。

## 6. 可扩展方向

后续可以继续增加：

- RTSP / USB 工业相机直连；
- 跨帧目标跟踪与唯一器件 ID；
- 批量文件夹检测；
- ONNX / TensorRT / OpenVINO 加速；
- 自定义类别配置；
- 元器件缺失检测；
- 标准板与待测板差异比对；
- 计数准确率专项评估；
- REST API 或 Web 服务部署；
- PCB 缺陷检测与元器件识别联合分析。
