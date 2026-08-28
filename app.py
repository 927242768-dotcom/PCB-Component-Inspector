from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcb_inspector.detector import ComponentDetector
from pcb_inspector.model_registry import ensure_default_model
from pcb_inspector.reporting import build_json_report, detections_to_csv, summarize
from pcb_inspector.visualize import draw_detections


st.set_page_config(page_title="PCB 元器件识别与统计", page_icon="🔬", layout="wide")
st.title("🔬 PCB 元器件识别与统计系统")
st.caption("YOLO 元器件检测 · 自动分类计数 · 小目标切片推理 · CSV / JSON 结果导出")


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
    imgsz = st.select_slider("推理分辨率", options=[640, 768, 960, 1024, 1280, 1536], value=1280)
    use_tile = st.checkbox("启用小目标切片推理", value=True, help="PCB 分辨率较高、元器件很小时建议开启")
    tile_size = st.select_slider("切片尺寸", options=[640, 768, 960, 1024, 1280], value=1024, disabled=not use_tile)
    overlap = st.slider("切片重叠", 0.05, 0.40, 0.20, 0.05, disabled=not use_tile)

uploaded = st.file_uploader("上传 PCB 图片", type=["jpg", "jpeg", "png", "bmp", "webp"])

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
    if model_mode == "自动下载默认开源模型":
        with st.spinner("准备开源 PCB 元器件模型…"):
            model_path = ensure_default_model(ROOT / "models")
    else:
        model_path = Path(custom_model)
        if not model_path.exists():
            st.error(f"找不到模型：{model_path}")
            st.stop()

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
        summary = summarize(detections)

    with right:
        st.subheader("识别结果")
        st.image(annotated_rgb, use_container_width=True)

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

    ok, encoded = cv2.imencode(".jpg", annotated_bgr)
    st.subheader("导出")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button("下载标注图片", encoded.tobytes() if ok else b"", file_name="pcb_annotated.jpg", mime="image/jpeg", use_container_width=True)
    with d2:
        st.download_button("下载 CSV 明细", detections_to_csv(detections).encode("utf-8-sig"), file_name="pcb_detections.csv", mime="text/csv", use_container_width=True)
    with d3:
        st.download_button("下载 JSON 报告", build_json_report(detections).encode("utf-8"), file_name="pcb_report.json", mime="application/json", use_container_width=True)
