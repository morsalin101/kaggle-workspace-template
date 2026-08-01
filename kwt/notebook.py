"""Prepare the code file that gets pushed to Kaggle.

The tracked notebook stays clean: the bootstrap cell that puts the synced
`src/` dataset on `sys.path` is added only to the copy in `.build/`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import Config, ConfigError
from .metadata import code_file_name

BOOTSTRAP_MARKER = "# --- kwt bootstrap (auto-generated, do not edit) ---"


def bootstrap_source(cfg: Config) -> list[str]:
    """The lines of the injected cell, one string per line (nbformat style).

    The mount point is *discovered*, not hardcoded: Kaggle currently mounts
    datasets at /kaggle/input/datasets/<owner>/<slug> but has used
    /kaggle/input/<slug> in the past, so we probe both and fall back to a
    shallow walk. Sub-packages arrive as .zip archives when Kaggle does not
    expand them itself, so any leftovers are unpacked into /kaggle/working.
    """
    slug = cfg.src_dataset_slug
    owner = cfg.username
    return [
        f"{BOOTSTRAP_MARKER}\n",
        "# Puts this project's synced `src/` on the import path.\n",
        "import sys, os, glob, zipfile\n",
        "\n",
        f'_KWT_SLUG = "{slug}"\n',
        f'_KWT_OWNER = "{owner}"\n',
        '_KWT_UNPACKED = "/kaggle/working/_kwt_src"\n',
        "\n",
        "def _kwt_locate():\n",
        "    for _c in (f'/kaggle/input/datasets/{_KWT_OWNER}/{_KWT_SLUG}',\n",
        "               f'/kaggle/input/{_KWT_SLUG}'):\n",
        "        if os.path.isdir(_c):\n",
        "            return _c\n",
        "    for _root, _dirs, _ in os.walk('/kaggle/input'):\n",
        "        if _KWT_SLUG in _dirs:\n",
        "            return os.path.join(_root, _KWT_SLUG)\n",
        "        if _root.count(os.sep) > 5:\n",
        "            _dirs[:] = []\n",
        "    return None\n",
        "\n",
        "_KWT_SRC = _kwt_locate()\n",
        "if _KWT_SRC is None:\n",
        "    print(f'[kwt] warning: dataset {_KWT_SLUG} is not attached — '\n",
        "          'imports from src/ will fail')\n",
        "else:\n",
        "    for _zip in glob.glob(os.path.join(_KWT_SRC, '*.zip')):\n",
        "        with zipfile.ZipFile(_zip) as _zf:\n",
        "            _zf.extractall(_KWT_UNPACKED)\n",
        "    for _path in (_KWT_SRC, _KWT_UNPACKED):\n",
        "        if os.path.isdir(_path) and _path not in sys.path:\n",
        "            sys.path.insert(0, _path)\n",
    ]


def _new_code_cell(source: list[str]) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


def is_bootstrap_cell(cell: dict) -> bool:
    """True for a cell this tool generated (identified by its marker comment)."""
    source = cell.get("source", "")
    text = source if isinstance(source, str) else "".join(source)
    return cell.get("cell_type") == "code" and BOOTSTRAP_MARKER in text


def strip_bootstrap(nb: dict) -> tuple[dict, int]:
    """Remove every generated cell. Returns the notebook and how many went."""
    cells = nb.get("cells", [])
    kept = [cell for cell in cells if not is_bootstrap_cell(cell)]
    nb["cells"] = kept
    return nb, len(cells) - len(kept)


def read_notebook(path: Path) -> dict:
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not valid notebook JSON: {exc}") from exc
    if not isinstance(blob, dict) or "cells" not in blob:
        raise ConfigError(f"{path} has no 'cells' key — is it really a notebook?")
    return blob


def inject_bootstrap(notebook: dict, cfg: Config) -> dict:
    """Ensure exactly one bootstrap cell sits at the top of the notebook."""
    notebook, _ = strip_bootstrap(notebook)
    notebook["cells"] = [_new_code_cell(bootstrap_source(cfg)), *notebook["cells"]]
    return notebook


def stage(cfg: Config) -> Path:
    """Copy the project's code file into the build dir, injecting if configured.

    Returns the path of the staged code file.
    """
    source = cfg.notebook_path
    if not source.is_file():
        raise ConfigError(f"Notebook not found: {source}")

    destination = cfg.build_path / code_file_name(cfg)
    destination.parent.mkdir(parents=True, exist_ok=True)

    inject = (
        cfg.src_enabled
        and cfg["src"]["inject_bootstrap"]
        and source.suffix == ".ipynb"
    )
    if inject:
        notebook = inject_bootstrap(read_notebook(source), cfg)
        destination.write_text(json.dumps(notebook, indent=1) + "\n", encoding="utf-8")
    else:
        shutil.copyfile(source, destination)

    return destination


def blank_notebook(cells: list[dict]) -> dict:
    """A minimal but valid nbformat 4.4 document."""
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }


def markdown_cell(source: list[str]) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def code_cell(source: list[str]) -> dict:
    return _new_code_cell(source)
