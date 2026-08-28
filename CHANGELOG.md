# Changelog

本项目遵循语义化版本（Semantic Versioning）。

## [2.0.0] - 2026-08-28

### Added

- 新增 FPGA AXI4-Stream 实时图像预处理数据通路：RGB888 转灰度、3×3 Sobel、可配置阈值化。
- 新增两级行缓存 + 横向移位寄存器的 3×3 窗口 RTL，实现 1 pixel/clock 流式结构。
- 新增 AXI4-Lite 控制寄存器组，支持 ARM 动态控制 Sobel、阈值使能和阈值参数。
- 新增 ARM Linux UIO/mmap 寄存器控制模块 `pcb_inspector.fpga`。
- 新增 `scripts/fpga_ctl.py` FPGA 控制工具与 `scripts/arm_fpga_realtime.py` ARM+FPGA+YOLO 实时演示入口。
- 新增 FPGA/ARM 架构、上板验收和 FPGA 简历项目文档。
- 新增 FPGA 控制面自动测试。

### Changed

- 项目定位升级为 FPGA + ARM 异构实时 PCB 元器件视觉检测系统。
- 版本升级至 2.0.0；保留原有图片、视频和浏览器摄像头纯软件模式作为兼容路径。

## [1.1.0] - 2026-08-28

### Added

- 新增浏览器摄像头 WebRTC 实时检测模式，可持续返回带检测框、置信度和分类计数的视频流。
- 新增本地视频文件逐帧检测与结果视频导出。
- 新增视频逐帧检测流水线，可设置每 N 帧执行一次 YOLO 推理以平衡实时性与算力占用。
- 视频/实时模式支持独立推理分辨率、切片开关和切片参数。
- 新增视频检测单元测试与实时使用文档。
- 完善 GitHub Issue / Pull Request 模板、Dependabot 与版本发布工作流。

### Changed

- Streamlit 首页输入方式扩展为“上传图片 / 上传视频 / 实时摄像头”。
- 项目版本升级至 1.1.0，并增加 `streamlit-webrtc` 与 PyAV 依赖。

## [1.0.0] - 2026-08-28

### Added

- PCB 21 类元器件 YOLOv8 检测基础链路。
- 自动下载公开 PCB YOLOv8s 权重。
- 整图高分辨率推理。
- 面向小目标的重叠切片推理。
- 跨切片按类别 NMS 去重，减少重复计数。
- 元器件总数与分类数量统计。
- 标注图片、CSV 明细、JSON 报告导出。
- Streamlit 图形界面。
- 命令行入口。
- 自定义数据集训练/微调脚本。
- 数据集与精度提升文档。
- 系统架构与算法流程文档。
- 第三方依赖与许可证说明。
- GitHub Actions 自动测试。
- GitHub Release 维护规范。
