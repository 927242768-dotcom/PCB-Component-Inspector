# Changelog

本项目遵循语义化版本（Semantic Versioning）。

## [2.1.0] - 2026-08-28

### Added

- 新增紫光同创 `PG2L100H-6-FBG484` + RK3568 的实际板级目标支持，FPGA 工具链固定为 PDS 2022.2-SP6.4。
- 新增 PG2L100H 专用 128-bit PCIe BAR0 图像预处理 RTL，支持 3×3 Gaussian、Sobel、动态阈值、ROI、旁路和状态统计。
- 新增 64 KB 单 BAR0 共享窗口协议，默认使用 112×64 Gray8 帧，状态签名为 `0x50434250`。
- 新增 RK3568 Linux `resource0` mmap 客户端，实现 FPGA 配置、灰度帧写入、start/done 握手和输出读回。
- 新增 PG2L100H 板级 FDC、PDS 本地工程生成器、PCIe 热下载后重枚举脚本与板端一键运行脚本。
- 新增 PG2L100H/PDS 架构、上板、简历与面试说明文档。
- 新增 BAR0 协议、帧尺寸、状态解析与 mmap 文件后端测试；测试总数增至 12 项。
- GitHub CI/Release 增加 PG2L100H 专用 RTL 的 Icarus Verilog 编译检查。

### Changed

- 板端主路径由通用 UIO/VDMA 描述切换为 PG2L100H PCIe Endpoint + RK3568 `resource0` 的实际通信方式。
- ARM 实时入口改为高清原图 YOLO 与 112×64 FPGA 预处理双路径并行架构。
- 项目版本升级至 2.1.0。
- 文档补充同一 PG2L100H + RK3568 + PCIe 100H 平台的已上板 PDS 实现基线：250/125 MHz 用户时钟、WNS +0.558/+0.492 ns、LUT/REG/DRM 约 15.2%/3.7%/44.8%，并明确其为平台基线而非 PCB 专用核独立测量值。

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
