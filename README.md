# PCB-Component-Inspector

一个独立的 **PCB 板载元器件识别、分类、自动计数与检测报告系统**。

项目面向电子板卡图像分析场景，使用 YOLOv8 对 PCB 图像中的多类别、密集、小尺寸元器件进行目标检测，并在检测结果基础上完成分类计数、坐标记录、置信度统计、可视化标注以及 CSV / JSON 报告导出。

## 核心功能

- YOLOv8 PCB 元器件目标检测
- 默认支持 21 类板载对象：battery、button、buzzer、capacitor、clock、connector、diode、display、fuse、heatsink、ic、inductor、led、pads、pins、potentiometer、relay、resistor、switch、transformer、transistor
- 自动统计每一类元器件数量和总数量
- 高分辨率 PCB **切片推理**，提升小电阻、小电容等小目标的可见度
- 跨切片按类别 NMS 去重，降低重叠区域重复计数
- Streamlit 图形界面，支持图片、视频文件和浏览器摄像头三种输入方式
- 浏览器摄像头 WebRTC 实时检测，持续叠加检测框、置信度和当前分类计数
- 本地视频逐帧检测，并导出带标注的结果视频
- 视频检测支持“每 N 帧推理一次”，在实时性和算力占用之间灵活平衡
- 命令行批处理入口
- 输出标注图片、CSV 逐目标明细、JSON 汇总报告
- 支持替换任意 Ultralytics 兼容 `.pt` / `.onnx` 权重
- 提供自定义数据集训练与微调脚本
- GitHub Actions 自动测试
- 语义化版本与 GitHub Release 发布规范

## 系统流程

```text
PCB 图片
   │
   ├─ 整图推理 ─────────────────────┐
   │                                │
   └─ 高分辨率切片推理              │
          │                         │
          └─ 坐标还原               │
                 │                  │
                 └──────┬───────────┘
                        │
                  按类别全局 NMS
                        │
                 元器件检测结果
                        │
          ┌─────────────┼─────────────┐
          │             │             │
       分类计数       可视化标注    结构化明细
          │             │             │
       汇总统计       JPG/PNG      CSV / JSON
```

详细架构见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 默认开源模型

首次运行时，程序可自动下载公开 PCB 元器件检测模型：

- Model: `Arshia82sbn/pcb-yolov8s-detection`
- File: `best.pt`
- Source: https://huggingface.co/Arshia82sbn/pcb-yolov8s-detection
- Architecture: YOLOv8s
- Classes: 21

公开模型卡给出的部分 AP 包括：IC 0.801、resistor 0.635、capacitor 0.587、diode 0.556、connector 0.602。

这些指标只代表公开模型对应测试数据上的表现。不同 PCB 的封装、尺寸、拍摄角度、光照和背景差异较大，因此如果要在固定板型、固定相机或产线环境中获得更高准确率，应使用真实业务图片进行标注和微调。

## 第三方依赖与数据来源

项目使用或支持以下公开技术与资源：

- Ultralytics YOLO: https://github.com/ultralytics/ultralytics
- PCB 21-class model: https://huggingface.co/Arshia82sbn/pcb-yolov8s-detection
- FPIC Component dataset: https://github.com/dataset-ninja/fpic-component
- PCB Component Detection dataset/tooling: https://github.com/s39674/PCB-Component-Detection
- PCB Component Detection YOLOv8 dataset/project: https://github.com/TalhaAlvi1/pcb-component-detection-yolov8

这些资源仅作为依赖、模型来源或数据来源列出。项目自身的检测、切片、去重、统计、报告、界面和工程组织均在本仓库中独立实现。

详细许可证信息见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

## 环境要求

建议环境：

- Windows 10 / 11
- Python 3.10 / 3.11
- CPU 可运行推理
- NVIDIA GPU + CUDA 可显著加速推理和训练

## 安装

```bash
git clone https://github.com/927242768-dotcom/PCB-Component-Inspector.git
cd PCB-Component-Inspector
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

下载默认模型：

```bash
python scripts/download_model.py
```

模型默认保存到 `models/`。模型大文件、训练数据和训练输出不会提交到 Git 仓库。

## 图形界面

```bash
streamlit run app.py
```

操作流程：

1. 在首页选择输入方式：`上传图片`、`上传视频` 或 `实时摄像头`；
2. 设置置信度阈值和推理分辨率；
3. 静态高清 PCB 图片可开启切片推理；实时视频建议先关闭切片；
4. 图片模式点击“开始识别并统计”，可导出标注图、CSV 和 JSON；
5. 视频模式点击“开始视频检测”，可导出带检测框和当前计数的结果视频；
6. 实时摄像头模式点击 WebRTC 的 `START`，允许浏览器访问摄像头后即可持续检测。

实时模式默认建议使用 640 推理分辨率、每 2~3 帧检测一次。CPU 环境下这样通常更流畅；GPU 性能充足时可设置为每帧检测。远程部署摄像头模式时浏览器需要 HTTPS，本机通过 `localhost` 使用不受影响。

更详细说明见 [`docs/VIDEO_AND_CAMERA.md`](docs/VIDEO_AND_CAMERA.md)。

## 命令行使用

安装为可编辑包后：

```bash
pcb-inspect path/to/pcb.jpg --imgsz 1280 --tile 1024 --overlap 0.20
```

也可以直接运行：

```bash
python -m pcb_inspector.cli path/to/pcb.jpg --imgsz 1280 --tile 1024
```

默认输出：

```text
outputs/
├─ xxx_annotated.jpg
├─ xxx_detections.csv
└─ xxx_report.json
```

## 自定义权重

```bash
pcb-inspect pcb.jpg --model runs/detect/pcb_components_v1/weights/best.pt
```

Streamlit 页面同样支持输入本地权重路径。

## 训练与微调

准备 YOLO 格式数据集后：

```bash
python scripts/train.py \
  --data configs/pcb_components.yaml \
  --weights yolov8s.pt \
  --epochs 150 \
  --imgsz 1280
```

训练输出默认位于：

```text
runs/detect/pcb_components_v1/weights/best.pt
```

### 为什么默认使用 1280 输入尺寸

PCB 上很多元器件属于小目标。整块板缩放到 640×640 后，小封装器件可能只剩很少像素，导致漏检率明显上升。因此项目默认提供更高输入分辨率，并进一步加入切片推理，让模型在局部区域看到更多像素细节。

## 项目结构

```text
PCB-Component-Inspector/
├─ app.py                         # Streamlit 图形界面
├─ configs/
│  └─ pcb_components.yaml        # 21 类数据集配置
├─ docs/
│  ├─ ARCHITECTURE.md            # 系统架构与算法流程
│  └─ DATASET.md                 # 数据、标注与精度提升
├─ scripts/
│  ├─ download_model.py          # 下载默认公开权重
│  └─ train.py                   # 训练/微调
├─ src/pcb_inspector/
│  ├─ detector.py                # 检测、切片、NMS
│  ├─ model_registry.py          # 模型管理
│  ├─ reporting.py               # CSV / JSON / 统计
│  ├─ video.py                   # 视频/摄像头逐帧检测流水线
│  ├─ visualize.py               # 检测结果绘制
│  └─ cli.py                     # 命令行入口
├─ tests/                         # 自动测试
├─ .github/workflows/ci.yml      # GitHub Actions CI
├─ .github/workflows/release.yml # Tag 推送时自动创建 GitHub Release
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ LICENSE
├─ RELEASE_POLICY.md
├─ THIRD_PARTY_NOTICES.md
├─ requirements.txt
└─ pyproject.toml
```

## 精度提升建议

通用模型适合快速启动，但固定业务场景建议进一步训练：

1. 收集真实相机、真实光照下的 PCB 图片；
2. 建立统一、稳定的类别定义；
3. 精确标注密集小目标；
4. 划分 train / val / test，避免同一块板的近似图片泄漏到不同集合；
5. 基于预训练权重微调；
6. 分别查看每一类 Precision、Recall、mAP50、mAP50-95；
7. 对容易漏检的类别增加真实困难样本；
8. 在最终部署相机上重新验证计数准确率。

## Release 规范

从 `v1.0.0` 开始，可用版本更新必须：

1. 更新 `CHANGELOG.md`；
2. 通过自动测试；
3. 创建语义化版本 Tag，例如 `v1.1.0`；
4. 创建对应 GitHub Release；
5. Release Notes 写明新增功能、修复、兼容性变化和模型变化。

详见 [`RELEASE_POLICY.md`](RELEASE_POLICY.md)。

## License

本项目按 **GNU Affero General Public License v3.0 (AGPL-3.0)** 发布。

第三方模型、数据集和依赖仍分别受其原始许可证约束，具体见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
