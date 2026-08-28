from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download

DEFAULT_MODEL_REPO = "Arshia82sbn/pcb-yolov8s-detection"
DEFAULT_MODEL_FILENAME = "best.pt"


def ensure_default_model(model_dir: str | Path = "models") -> Path:
    """下载并返回默认 PCB 元器件检测模型路径。

    模型来自公开 Hugging Face 仓库，首次运行时下载，之后复用本地缓存。
    """
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    target = model_dir / DEFAULT_MODEL_FILENAME
    if target.exists() and target.stat().st_size > 0:
        return target

    downloaded = hf_hub_download(
        repo_id=DEFAULT_MODEL_REPO,
        filename=DEFAULT_MODEL_FILENAME,
        local_dir=str(model_dir),
    )
    return Path(downloaded)
