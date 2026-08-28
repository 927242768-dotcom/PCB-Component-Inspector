# Third-Party Notices

本项目使用以下第三方开源依赖、公开模型或数据资源。各资源仍受其自身许可证和使用条款约束。

## Ultralytics YOLO

- Project: https://github.com/ultralytics/ultralytics
- Usage: YOLO 训练、推理与导出 API
- Open-source license: AGPL-3.0
- Commercial option: Ultralytics Enterprise License

本仓库按 AGPL-3.0 发布，以满足当前开源使用方式下的许可证要求。

## PCB YOLOv8s 21-class model

- Model: `Arshia82sbn/pcb-yolov8s-detection`
- Source: https://huggingface.co/Arshia82sbn/pcb-yolov8s-detection
- Usage: 默认 PCB 元器件检测权重
- Model card license: MIT

模型文件不直接提交到本仓库，而是在首次运行时通过 `huggingface-hub` 下载。

## PCB Component Detection YOLOv8

- Project: https://github.com/TalhaAlvi1/pcb-component-detection-yolov8
- Usage: 公开 PCB 元器件数据、类别定义与训练结果信息来源之一
- License: 以其仓库当前 LICENSE 为准

## FPIC Component Dataset

- Project: https://github.com/dataset-ninja/fpic-component
- Usage: PCB 元器件公开数据来源之一
- License: 以该数据集仓库及原始数据源条款为准

## PCB-Component-Detection

- Project: https://github.com/s39674/PCB-Component-Detection
- Usage: PCB 元器件公开数据与格式转换工具来源之一
- License: 以其仓库当前 LICENSE 为准

## 项目自身代码

PCB-Component-Inspector 自身的切片调度、坐标还原、全局去重、分类计数、报告生成、可视化、命令行入口、图形界面及工程组织均在本仓库中独立实现。

第三方项目名称、链接与许可证信息仅用于履行依赖和来源披露义务，不表示本仓库属于任何第三方项目的派生仓库。
