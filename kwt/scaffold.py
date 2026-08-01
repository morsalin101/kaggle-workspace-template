"""Generate a new project folder under projects/.

Each project is self-contained — its own notebook, its own src/, its own
settings — so an ML baseline and a deep-learning run never step on each other.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import (
    CONFIG_NAME,
    PROJECTS_DIR,
    SLUG_RE,
    ConfigError,
    list_projects,
    set_active_project,
)
from .notebook import blank_notebook, code_cell, markdown_cell

CONFIG_TEMPLATE = """\
# ---------------------------------------------------------------------------
# {name} — Kaggle notebook settings
# Everything Kaggle lets you configure lives here. Edit, then `make push`.
# ---------------------------------------------------------------------------

title: "{title}"          # shown on Kaggle
slug: {slug}              # URL: kaggle.com/code/<your-username>/{slug}

notebook: notebook.ipynb  # the file that gets pushed
language: python          # python | r | rmarkdown
kernel_type: notebook     # notebook | script

private: true             # false publishes the notebook
accelerator: gpu          # none | gpu | tpu
                          #   The API can only turn the accelerator on or off.
                          #   The exact hardware (GPU T4 x2 vs P100, or which TPU)
                          #   is a dropdown in Kaggle's notebook editor:
                          #     make push  ->  cancel the auto-run  ->  pick the
                          #     hardware in the sidebar  ->  "Save & Run All"
                          #   Keep this set to gpu/tpu even when you pick in the UI:
                          #   every push rewrites the on/off switch from this file.
internet: true            # false = no network inside the run (required by some comps)

# ---------------------------------------------------------------------------
# Attach data. Add slugs here — never edit kernel-metadata.json by hand.
# ---------------------------------------------------------------------------
sources:
  datasets: []            # - "owner/dataset-slug"      e.g. "zillow/zecon"
  competitions: []        # - "competition-slug"        e.g. "titanic"
  kernels: []             # - "owner/kernel-slug"       reuse another notebook's output
  models: []              # - "owner/model/framework/variation/version"

# ---------------------------------------------------------------------------
# Your local Python code, shipped to Kaggle as a private dataset.
# Write modules in src/, import them in the notebook, keep them unit-testable.
# ---------------------------------------------------------------------------
src:
  enabled: true
  dir: src
  include_shared: false   # also bundle the repo-root shared/ folder
  dataset_slug: null      # default: "<slug>-src"
  dataset_title: null     # default: "<title> — source"
  inject_bootstrap: true  # add the sys.path cell to the pushed copy only

# ---------------------------------------------------------------------------
push:
  wait: false             # true = block until the Kaggle run finishes
  poll_interval: 15       # seconds between status checks while waiting
  timeout: null           # cap the run's length, in seconds

output:
  dir: outputs            # `make output` downloads here (gitignored)
"""

EXAMPLE_MODULE = '''\
"""Example module — runs locally *and* inside the Kaggle notebook.

`make push` uploads this folder as a private Kaggle dataset and the notebook's
bootstrap cell puts it on sys.path, so `from {module} import describe` works
in both places.
"""

from __future__ import annotations


def describe(name: str = "world") -> str:
    """Trivial placeholder so the round-trip is easy to verify."""
    return f"Hello from {module}, {{name}}!"
'''


def module_name(project: str) -> str:
    """A valid python identifier derived from the project name."""
    ident = re.sub(r"[^0-9a-zA-Z_]", "_", project).strip("_").lower()
    if not ident or ident[0].isdigit():
        ident = f"p_{ident}"
    return f"{ident}_lib"


def _notebook(project: str, module: str) -> dict:
    return blank_notebook(
        [
            markdown_cell(
                [
                    f"# {project}\n",
                    "\n",
                    "Edit this notebook locally, then `make push P="
                    f"{project}` to run it on Kaggle.\n",
                    "\n",
                    "The first cell of the *pushed* copy is added automatically "
                    "and puts `src/` on the import path — you will not see it here.\n",
                ]
            ),
            code_cell(
                [
                    "import os, sys\n",
                    "\n",
                    "print('python', sys.version.split()[0])\n",
                    "print('running on kaggle:', os.path.isdir('/kaggle/input'))\n",
                ]
            ),
            code_cell(
                [
                    f"from {module} import describe\n",
                    "\n",
                    f"print(describe('{project}'))\n",
                ]
            ),
            markdown_cell(
                [
                    "## Outputs\n",
                    "\n",
                    "Anything written to `/kaggle/working/` comes back with "
                    "`make output`.\n",
                ]
            ),
            code_cell(
                [
                    "from pathlib import Path\n",
                    "\n",
                    "out = Path('/kaggle/working') if os.path.isdir('/kaggle/working') "
                    "else Path('.')\n",
                    "(out / 'result.txt').write_text('it works\\n')\n",
                    "print('wrote', out / 'result.txt')\n",
                ]
            ),
        ]
    )


def create(project: str, *, activate: bool | None = None) -> Path:
    """Scaffold projects/<project>/. Returns its path."""
    project = project.strip()
    if not SLUG_RE.match(project):
        raise ConfigError(
            f"'{project}' is not a valid project name.\n"
            "Use lowercase letters, digits and single hyphens, e.g. dl-finetune"
        )

    root = PROJECTS_DIR / project
    if root.exists():
        raise ConfigError(
            f"projects/{project}/ already exists — refusing to overwrite it."
        )

    existing = list_projects()

    (root / "src").mkdir(parents=True)
    module = module_name(project)

    title = project.replace("-", " ").title()
    (root / CONFIG_NAME).write_text(
        CONFIG_TEMPLATE.format(name=project, title=title, slug=project),
        encoding="utf-8",
    )

    (root / "notebook.ipynb").write_text(
        json.dumps(_notebook(project, module), indent=1) + "\n", encoding="utf-8"
    )

    (root / "src" / f"{module}.py").write_text(
        EXAMPLE_MODULE.format(module=module), encoding="utf-8"
    )

    outputs = root / "outputs"
    outputs.mkdir()
    (outputs / ".gitkeep").write_text("", encoding="utf-8")

    if activate or (activate is None and not existing):
        set_active_project(project)

    return root
