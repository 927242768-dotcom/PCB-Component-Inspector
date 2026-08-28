# 数据集与精度提升指南

## 1. 默认模型

项目默认通过 Hugging Face 下载 `Arshia82sbn/pcb-yolov8s-detection` 的 `best.pt`。
该模型用于 21 类 PCB 元器件检测，可作为开箱即用的通用基线。

默认类别：battery、button、buzzer、capacitor、clock、connector、diode、display、fuse、heatsink、ic、inductor、led、pads、pins、potentiometer、relay、resistor、switch、transformer、transistor。

## 2. 可用的公开数据来源

### FICS / FPIC Component

- 用途：PCB 元器件检测、实例/语义分割。
- 数据量较大，可用于补充元器件外观多样性。
- Source: https://github.com/dataset-ninja/fpic-component

### PCB Component Detection / WACV 2019 类数据

- 典型类别：resistor、capacitor、inductor、diode、led、ic、transistor、connector、fuse、buzzer 等。
- 数据转换工具来源：https://github.com/s39674/PCB-Component-Detection

### PCB Component Detection YOLOv8

- Source: https://github.com/TalhaAlvi1/pcb-component-detection-yolov8
- 可用于获取公开数据、类别定义与公开训练结果信息。

使用任何公开数据前，都应单独确认其数据许可和再分发条件。

## 3. 为什么不能只靠通用权重保证“准确”

PCB 小目标主要有三个难点：

1. 电阻、电容等尺寸小、数量多；
2. 不同板卡拍摄角度、光照、丝印和封装差异大；
3. 同一类别内部差异大，而不同类别有时外观相似。

因此，如果需要在固定板型、固定相机或固定产线环境中获得更高准确率，应补充实际场景的标注图片进行微调。

## 4. 推荐采集方式

- 相机尽量垂直 PCB；
- 分辨率建议不低于 1920×1080，条件允许时使用更高分辨率；
- 同一块板拍摄多种光照与轻微角度；
- 保留不同背景、焦距和曝光；
- 小元器件框尽量贴合，不要把多个元器件框成一个大框；
- 类别命名保持稳定，避免 `IC` / `ic` 这类重复类别；
- 对高密度区域进行放大检查，减少漏标和错标。

## 5. YOLO 数据目录

```text
dataset/
├─ images/
│  ├─ train/
│  ├─ val/
│  └─ test/
└─ labels/
   ├─ train/
   ├─ val/
   └─ test/
```

每个标签文件一行：

```text
class_id x_center y_center width height
```

坐标均归一化到 0~1。

## 6. 数据集划分

建议：

- train：70%~80%；
- val：10%~20%；
- test：10%~20%。

如果同一块 PCB 拍摄了大量相似照片，应尽量按“板卡实例/拍摄批次”划分，而不是简单随机拆图，避免相似图片同时进入训练集和测试集造成指标虚高。

## 7. 训练

```bash
python scripts/train.py --data configs/pcb_components.yaml --weights yolov8s.pt --epochs 150 --imgsz 1280
```

有 NVIDIA GPU 时：

```bash
python scripts/train.py --device 0 --batch 8
```

只有 CPU 时也可以训练，但速度会很慢。推理仍可在普通电脑上运行。

## 8. 小目标策略

项目推理阶段提供切片推理：把高分辨率 PCB 分成多个重叠区域分别检测，再进行全局按类别 NMS 去重。这样小电阻、小电容在模型输入中占据更多像素，通常比直接将整张高分辨率图片大幅缩小更有利。

建议参数：

- 普通板卡：`imgsz=1280`；
- 超高分辨率板卡：`tile=1024` 或 `1280`，`overlap=0.20`；
- 漏检较多：可适当降低 `conf`，同时检查误检是否增加；
- 重复框较多：检查 overlap 与全局 NMS IoU；
- 小器件特别密集：优先提高拍摄清晰度和真实训练样本质量，而不是无限降低置信度。

## 9. 评估建议

除了模型常规的 Precision、Recall、mAP50、mAP50-95，还建议为实际业务增加：

- 每类计数准确率；
- 单张 PCB 总数量误差；
- 漏检数 / 误检数；
- 小目标尺寸分段评估；
- 不同光照、角度、相机条件下的稳定性测试。
