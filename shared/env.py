"""Small helpers for code that must run both locally and on Kaggle."""

from __future__ import annotations

import os
from pathlib import Path


def on_kaggle() -> bool:
    """True when executing inside a Kaggle kernel."""
    return Path("/kaggle/input").is_dir()


def input_dir() -> Path:
    """Root of the attached data: /kaggle/input on Kaggle, ./data locally."""
    return Path("/kaggle/input") if on_kaggle() else Path("data")


def find_input(slug: str, *, max_depth: int = 5) -> Path:
    """Locate an attached dataset/competition by slug, whatever the mount layout.

    Kaggle currently mounts datasets under /kaggle/input/datasets/<owner>/<slug>
    but has used a flat /kaggle/input/<slug> before, so probe rather than assume.
    Raises FileNotFoundError listing what *is* attached, which beats debugging a
    silent empty read.
    """
    base = input_dir()
    direct = base / slug
    if direct.is_dir():
        return direct

    for root, dirs, _ in os.walk(base):
        if slug in dirs:
            return Path(root) / slug
        if root.count(os.sep) > max_depth:
            dirs[:] = []

    attached = [str(p.relative_to(base)) for p in base.rglob("*") if p.is_dir()][:20]
    raise FileNotFoundError(
        f"No attached source named '{slug}' under {base}.\n"
        f"Attached: {attached or '(nothing)'}\n"
        "Add it to `sources:` in config.yml and re-run `make push`."
    )


def working_dir() -> Path:
    """Where to write results so `make output` can bring them back."""
    path = Path("/kaggle/working") if on_kaggle() else Path("outputs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def accelerator() -> str:
    """Report the accelerator actually available at runtime: cuda | tpu | cpu."""
    if os.environ.get("TPU_NAME") or os.environ.get("COLAB_TPU_ADDR"):
        return "tpu"
    try:
        import torch  # noqa: PLC0415 - optional dependency

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"
