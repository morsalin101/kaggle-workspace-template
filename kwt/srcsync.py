"""Publish a project's `src/` folder as a private Kaggle utility dataset.

This is what lets you write real, testable `.py` modules locally instead of
stuffing every helper into a notebook cell. On each push the folder is staged,
uploaded as a new dataset version, and attached to the kernel.

Note on layout: the Kaggle CLI uploads top-level files as-is and packs each
sub-folder into a single archive, so we stage the *contents* of `src/` at the
top level. A package `src/mylib/` therefore arrives as `mylib.zip`, which
Kaggle expands back into `mylib/` — and the injected bootstrap cell unpacks it
itself if Kaggle happens not to.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from . import kaggle_cli
from .config import SHARED_DIR, Config, ConfigError
from .metadata import dataset_metadata, write

EXCLUDE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".ipynb_checkpoints", ".DS_Store", "*.egg-info"
)

READY_STATES = ("ready", "complete")
ERROR_STATES = ("error", "failed")


def stage(cfg: Config) -> Path:
    """Copy src/ (and optionally shared/) into the build dir. Returns that dir."""
    staging = cfg.build_path / "_src"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    src = cfg.src_path
    if not src.is_dir():
        raise ConfigError(
            f"src.enabled is true but {src} does not exist.\n"
            "Create the folder, or set `src: {enabled: false}` in config.yml"
        )

    for item in sorted(src.iterdir()):
        if item.name in {"__pycache__", ".ipynb_checkpoints", ".DS_Store"}:
            continue
        target = staging / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=EXCLUDE)
        else:
            shutil.copyfile(item, target)

    if cfg["src"]["include_shared"]:
        if not SHARED_DIR.is_dir():
            raise ConfigError(f"src.include_shared is true but {SHARED_DIR} is missing.")
        shutil.copytree(SHARED_DIR, staging / SHARED_DIR.name, ignore=EXCLUDE)

    payload = [p for p in staging.rglob("*") if p.is_file()]
    if not payload:
        raise ConfigError(
            f"Nothing to upload: {src} contains no files.\n"
            "Add a module, or set `src: {enabled: false}` in config.yml"
        )

    write(dataset_metadata(cfg), staging / "dataset-metadata.json")
    return staging


def exists(cfg: Config) -> bool:
    """Has this src dataset been created on Kaggle yet?"""
    result = kaggle_cli.run("datasets", "status", cfg.src_dataset_id, check=False)
    if result.ok:
        return "404" not in result.text and "not found" not in result.text.lower()
    return False


def status(cfg: Config) -> str:
    result = kaggle_cli.run("datasets", "status", cfg.src_dataset_id, check=False)
    return (result.text or "unknown").strip().lower()


def wait_until_ready(cfg: Config, *, interval: int = 5, timeout: int = 300) -> str:
    def done(state: str) -> bool:
        return any(s in state for s in READY_STATES + ERROR_STATES)

    return kaggle_cli.poll(
        lambda: status(cfg), done, interval=interval, timeout=timeout
    )


def sync(cfg: Config, *, message: str | None = None, quiet: bool = False) -> str:
    """Create or version the src dataset. Returns its `owner/slug` id."""
    staging = stage(cfg)
    file_count = sum(1 for p in staging.rglob("*") if p.is_file()) - 1  # minus metadata

    if exists(cfg):
        note = message or f"kwt sync: {cfg.name}"
        _say(quiet, f"  updating dataset {cfg.src_dataset_id} ({file_count} file(s))")
        kaggle_cli.run(
            "datasets", "version",
            "-p", str(staging),
            "-m", note,
            "--dir-mode", "zip",
            "-q",
        )
    else:
        _say(quiet, f"  creating dataset {cfg.src_dataset_id} ({file_count} file(s))")
        # No -u/--public: the dataset stays private, like your code should.
        kaggle_cli.run(
            "datasets", "create",
            "-p", str(staging),
            "--dir-mode", "zip",
            "-q",
        )

    state = wait_until_ready(cfg)
    if any(bad in state for bad in ERROR_STATES):
        raise kaggle_cli.KaggleError(
            f"Kaggle failed to process {cfg.src_dataset_id}: {state}"
        )
    _say(quiet, f"  dataset ready: {cfg.src_dataset_id}")
    return cfg.src_dataset_id


def _say(quiet: bool, message: str) -> None:
    if not quiet:
        print(message, file=sys.stderr)
