from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import av
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_webrtc import webrtc_streamer

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcb_inspector.detector import ComponentDetector
from pcb_inspector.model_registry import ensure_default_model
from pcb_inspector.reporting import build_json_report, detections_to_csv, summarize
from pcb_inspector.video import FrameDetectionPipeline, FrameInferenceSettings
from pcb_inspector.visualize import draw_detections


st.set_page_config(page_title="PCB 元器件识别与统计", page_icon="🔬", layout="wide")
st.title("🔬 PCB 元器件识别与统计系统")
st.caption("YOLO 元器件检测 · 图片/视频/摄像头实时识别 · 自动分类计数 · CSV / JSON 结果导出")

source_mode = st.radio(
    "输入方式",
    ["上传图片", "上传视频", "实时摄像头"],
    horizontal=True,
    help="实时摄像头会直接调用浏览器摄像头，并在视频画面上持续绘制检测框和当前计数。",
)


@st.cache_resource(show_spinner=False)
def load_detector(model_path: str) -> ComponentDetector:
    return ComponentDetector(model_path)


with st.sidebar:
    st.header("识别设置")
    model_mode = st.radio("模型来源", ["自动下载默认开源模型", "使用本地权重"], index=0)
    custom_model = ""
    if model_mode == "使用本地权重":
        custom_model = st.text_input("本地 .pt/.onnx 权重路径", value="models/best.pt")

    conf = st.slider("置信度阈值", 0.05, 0.95, 0.25, 0.05)
    iou = st.slider("NMS IoU", 0.10, 0.90, 0.45, 0.05)

    if source_mode == "上传图片":
        imgsz = st.select_slider("推理分辨率", options=[640, 768, 960, 1024, 1280, 1536], value=1280)
        use_tile = st.checkbox("启用小目标切片推理", value=True, help="PCB 分辨率较高、元器件很小时建议开启")
        tile_size = st.select_slider(
            "切片尺寸",
            options=[640, 768, 960, 1024, 1280],
            value=1024,
            disabled=not use_tile,
        )
        overlap = st.slider("切片重叠", 0.05, 0.40, 0.20, 0.05, disabled=not use_tile)
        detect_every = 1
    else:
        st.subheader("视频性能")
        imgsz = st.select_slider("视频推理分辨率", options=[416, 512, 640, 768, 960, 1024], value=640)
        detect_every = st.select_slider(
            "每 N 帧执行一次检测",
            options=[1, 2, 3, 4, 5, 6, 8, 10],
            value=2,
            help="CPU 推理建议 2~5；GPU 性能足够时可设为 1。中间帧会沿用最近一次检测框。",
        )
        use_tile = st.checkbox(
            "视频模式启用切片推理",
            value=False,
            help="切片推理更适合静态高清图片。实时视频开启后会明显降低帧率。",
        )
        tile_size = st.select_slider(
            "视频切片尺寸",
            options=[640, 768, 960, 1024],
            value=768,
            disabled=not use_tile,
        )
        overlap = st.slider("视频切片重叠", 0.05, 0.35, 0.15, 0.05, disabled=not use_tile)


def get_model_path() -> Path:
    if model_mode == "自动下载默认开源模型":
        with st.spinner("准备开源 PCB 元器件模型…"):
            return ensure_default_model(ROOT / "models")

    model_path = Path(custom_model).expanduser()
    if not model_path.is_absolute():
        model_path = ROOT / model_path
    if not model_path.exists():
        st.error(f"找不到模型：{model_path}")
        st.stop()
    return model_path


def build_frame_settings() -> FrameInferenceSettings:
    return FrameInferenceSettings(
        conf=conf,
        iou=iou,
        imgsz=imgsz,
        tile_size=tile_size if use_tile else None,
        tile_overlap=overlap,
    )


def render_detection_tables(detections) -> None:
    summary = summarize(detections)
    st.success(f"识别完成：共检测到 {len(detections)} 个元器件，涉及 {len(summary)} 个类别。")

    c1, c2, c3 = st.columns(3)
    c1.metric("元器件总数", len(detections))
    c2.metric("识别类别数", len(summary))
    avg_conf = sum(d.confidence for d in detections) / len(detections) if detections else 0.0
    c3.metric("平均置信度", f"{avg_conf:.1%}")

    st.subheader("分类统计")
    summary_df = pd.DataFrame([{"元器件类别": name, "数量": count} for name, count in summary.items()])
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.subheader("逐目标明细")
    detail_df = pd.DataFrame([d.to_dict() for d in detections])
    st.dataframe(detail_df, use_container_width=True, hide_index=True)


if source_mode == "上传图片":
    uploaded = st.file_uploader("上传 PCB 图片", type=["jpg", "jpeg", "png", "bmp", "webp"], key="image-upload")

    if uploaded is None:
        st.info("请上传一张 PCB 板图片。首次使用默认模型时会从公开模型仓库自动下载权重。")
        st.stop()

    pil_image = Image.open(uploaded).convert("RGB")
    rgb = np.asarray(pil_image)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    left, right = st.columns(2)
    with left:
        st.subheader("原始图片")
        st.image(rgb, use_container_width=True)

    if st.button("开始识别并统计", type="primary", use_container_width=True):
        model_path = get_model_path()
        with st.spinner("正在检测 PCB 上的元器件…"):
            detector = load_detector(str(model_path))
            detections = detector.predict(
                bgr,
                conf=conf,
                iou=iou,
                imgsz=imgsz,
                tile_size=tile_size if use_tile else None,
                tile_overlap=overlap,
            )
            annotated_bgr = draw_detections(bgr, detections, show_summary=True)
            annotated_rgb = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)

        with right:
            st.subheader("识别结果")
            st.image(annotated_rgb, use_container_width=True)

        render_detection_tables(detections)

        ok, encoded = cv2.imencode(".jpg", annotated_bgr)
        st.subheader("导出")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.download_button(
                "下载标注图片",
                encoded.tobytes() if ok else b"",
                file_name="pcb_annotated.jpg",
                mime="image/jpeg",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                "下载 CSV 明细",
                detections_to_csv(detections).encode("utf-8-sig"),
                file_name="pcb_detections.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with d3:
            st.download_button(
                "下载 JSON 报告",
                build_json_report(detections).encode("utf-8"),
                file_name="pcb_report.json",
                mime="application/json",
                use_container_width=True,
            )

elif source_mode == "上传视频":
    uploaded_video = st.file_uploader(
        "上传 PCB 视频",
        type=["mp4", "mov", "avi", "mkv", "webm", "m4v"],
        key="video-upload",
    )
    if uploaded_video is None:
        st.info("请上传 PCB 视频。系统会逐帧检测，并生成带检测框和当前分类计数的结果视频。")
        st.stop()

    st.subheader("原始视频")
    st.video(uploaded_video)

    if st.button("开始视频检测", type="primary", use_container_width=True):
        model_path = get_model_path()
        detector = load_detector(str(model_path))
        pipeline = FrameDetectionPipeline(detector, build_frame_settings(), detect_every=detect_every)

        input_path: Path | None = None
        output_path: Path | None = None
        cap = None
        writer = None
        try:
            suffix = Path(uploaded_video.name).suffix or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as input_file:
                input_file.write(uploaded_video.getvalue())
                input_path = Path(input_file.name)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as output_file:
                output_path = Path(output_file.name)

            cap = cv2.VideoCapture(str(input_path))
            if not cap.isOpened():
                st.error("无法打开该视频，请尝试 MP4/MOV/AVI 等常见格式。")
                st.stop()

            fps = float(cap.get(cv2.CAP_PROP_FPS))
            if not np.isfinite(fps) or fps <= 0:
                fps = 25.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if width <= 0 or height <= 0:
                st.error("无法读取视频分辨率。")
                st.stop()

            writer = cv2.VideoWriter(
                str(output_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (width, height),
            )
            if not writer.isOpened():
                st.error("无法创建结果视频文件。")
                st.stop()

            progress = st.progress(0.0)
            status = st.empty()
            processed = 0
            last_detections = []

            with st.spinner("正在逐帧检测视频…"):
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    annotated, last_detections = pipeline.process(frame)
                    writer.write(annotated)
                    processed += 1
                    if total_frames > 0 and (processed % 5 == 0 or processed == total_frames):
                        progress.progress(min(1.0, processed / total_frames))
                        status.caption(f"已处理 {processed}/{total_frames} 帧")

            cap.release()
            cap = None
            writer.release()
            writer = None
            progress.progress(1.0)
            status.caption(f"处理完成：{processed} 帧；实际执行 YOLO 推理约 {(processed + detect_every - 1) // detect_every} 次。")

            result_bytes = output_path.read_bytes()
            st.subheader("检测结果视频")
            st.video(result_bytes)
            st.download_button(
                "下载检测结果视频",
                data=result_bytes,
                file_name=f"{Path(uploaded_video.name).stem}_detected.mp4",
                mime="video/mp4",
                use_container_width=True,
            )

            st.caption("下方统计对应视频结束时最近一次检测结果；视频左上角会持续显示每一帧的当前计数。")
            render_detection_tables(last_detections)
        finally:
            if cap is not None:
                cap.release()
            if writer is not None:
                writer.release()
            if input_path is not None:
                input_path.unlink(missing_ok=True)
            if output_path is not None:
                output_path.unlink(missing_ok=True)

else:
    st.subheader("实时摄像头检测")
    st.write("点击下方 **START**，允许浏览器访问摄像头后，系统会持续识别画面中的 PCB 元器件并实时叠加检测框、置信度和分类计数。")
    st.info("实时模式建议先使用 640 分辨率、每 2~3 帧检测一次，并关闭切片推理；如果有 NVIDIA GPU，可逐步提高分辨率并改为每帧检测。")

    model_path = get_model_path()
    detector = load_detector(str(model_path))
    pipeline = FrameDetectionPipeline(detector, build_frame_settings(), detect_every=detect_every)

    def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
        image = frame.to_ndarray(format="bgr24")
        annotated, _ = pipeline.process(image)
        return av.VideoFrame.from_ndarray(annotated, format="bgr24")

    webrtc_streamer(
        key="pcb-live-detection",
        video_frame_callback=video_frame_callback,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=False,
    )

    st.caption("本机通过 http://localhost 访问时浏览器可直接请求摄像头权限；远程部署时需要 HTTPS。实时统计已直接叠加在返回的视频画面中。")
