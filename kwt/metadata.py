"""Render Kaggle metadata files from a validated Config.

Kept pure (Config in, dict out) so the mapping from config.yml to Kaggle's
schema is easy to read and easy to test without touching the network.

Reference: https://github.com/Kaggle/kaggle-api/wiki/Kernel-Metadata
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import Config

# Kaggle infers the code file's language from its extension; these are the
# filenames it expects for each (kernel_type, language) pair.
CODE_FILE_SUFFIX = {
    ("notebook", "python"): ".ipynb",
    ("notebook", "r"): ".ipynb",
    ("script", "python"): ".py",
    ("script", "r"): ".R",
    ("script", "rmarkdown"): ".Rmd",
    ("notebook", "rmarkdown"): ".Rmd",
}


def code_file_name(cfg: Config) -> str:
    """Name the code file gets inside the build directory."""
    suffix = CODE_FILE_SUFFIX.get(
        (cfg["kernel_type"], cfg["language"]), Path(cfg["notebook"]).suffix
    )
    return f"{cfg.slug}{suffix}"


def kernel_metadata(cfg: Config) -> dict:
    """Build the `kernel-metadata.json` payload."""
    accelerator = cfg["accelerator"]
    sources = cfg["sources"]

    dataset_sources = list(sources["datasets"])
    if cfg.src_enabled and cfg.src_dataset_id not in dataset_sources:
        dataset_sources.append(cfg.src_dataset_id)

    return {
        "id": cfg.kernel_id,
        "title": cfg.title,
        "code_file": code_file_name(cfg),
        "language": cfg["language"],
        "kernel_type": cfg["kernel_type"],
        "is_private": bool(cfg["private"]),
        "enable_gpu": accelerator == "gpu",
        "enable_tpu": accelerator == "tpu",
        "enable_internet": bool(cfg["internet"]),
        "dataset_sources": dataset_sources,
        "competition_sources": list(sources["competitions"]),
        "kernel_sources": list(sources["kernels"]),
        "model_sources": list(sources["models"]),
    }


def dataset_metadata(cfg: Config) -> dict:
    """Build the `dataset-metadata.json` payload for the src utility dataset."""
    return {
        "id": cfg.src_dataset_id,
        "title": cfg["src"]["dataset_title"],
        "licenses": [{"name": "CC0-1.0"}],
    }


def write(payload: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
