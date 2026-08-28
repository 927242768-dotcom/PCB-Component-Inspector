from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pcb_inspector.model_registry import ensure_default_model


if __name__ == "__main__":
    path = ensure_default_model(ROOT / "models")
    print(f"模型已准备：{path}")
