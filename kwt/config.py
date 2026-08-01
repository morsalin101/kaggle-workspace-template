"""Project configuration: locate, load, merge with defaults, and validate.

A project is a folder under `projects/` containing a `config.yml`. Everything a
user can tune about a Kaggle notebook lives in that one file; this module turns
it into a fully-populated, validated `Config` object.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

def _yaml():
    """Import PyYAML lazily.

    `kwt setup` is what *installs* PyYAML, so importing it at module scope would
    make setup fail with an instruction to run setup.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - surfaced with an actionable message
        raise ConfigError(
            "PyYAML is not installed.\n"
            "Run `make setup` (or `pip install -r requirements.txt`) first."
        ) from None
    return yaml


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT / "projects"
SHARED_DIR = REPO_ROOT / "shared"
BUILD_DIR = REPO_ROOT / ".build"
ACTIVE_FILE = PROJECTS_DIR / ".active"
ENV_FILE = REPO_ROOT / ".env"
CONFIG_NAME = "config.yml"

# Stands in for the username in offline output when no credentials exist yet.
PLACEHOLDER_USERNAME = "YOUR-KAGGLE-USERNAME"


class ConfigError(Exception):
    """Raised for any user-fixable problem in a project's configuration."""


# --------------------------------------------------------------------------
# Defaults — every key a config.yml may set, with its fallback value.
# --------------------------------------------------------------------------

DEFAULTS: dict = {
    "title": None,
    "slug": None,
    "notebook": "notebook.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "private": True,
    # GPU by default: this workspace exists to run things Kaggle's hardware is
    # good for. Set `accelerator: none` per project to stay on CPU quota.
    "accelerator": "gpu",
    "internet": True,
    "sources": {
        "datasets": [],
        "competitions": [],
        "kernels": [],
        "models": [],
    },
    "src": {
        "enabled": True,
        "dir": "src",
        "include_shared": False,
        "dataset_slug": None,
        "dataset_title": None,
        "inject_bootstrap": True,
    },
    "push": {
        "wait": False,
        "poll_interval": 15,
        "timeout": None,
    },
    "output": {
        "dir": "outputs",
    },
}

LANGUAGES = ("python", "r", "rmarkdown")
KERNEL_TYPES = ("notebook", "script")
ACCELERATORS = ("none", "gpu", "tpu")

# Kaggle slugs: lowercase alphanumerics and hyphens, 3-50 chars.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
OWNER_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
COMPETITION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
# owner/model/framework/variation/version
MODEL_RE = re.compile(r"^[^/]+/[^/]+/[^/]+/[^/]+/[^/]+$")


@dataclass
class Config:
    """A fully resolved project configuration."""

    name: str
    root: Path
    username: str
    data: dict = field(repr=False, default_factory=dict)

    # -- convenience accessors -------------------------------------------
    def __getitem__(self, key):
        return self.data[key]

    @property
    def title(self) -> str:
        return self.data["title"]

    @property
    def slug(self) -> str:
        return self.data["slug"]

    @property
    def kernel_id(self) -> str:
        return f"{self.username}/{self.slug}"

    @property
    def kernel_url(self) -> str:
        return f"https://www.kaggle.com/code/{self.username}/{self.slug}"

    @property
    def notebook_path(self) -> Path:
        return self.root / self.data["notebook"]

    @property
    def src_enabled(self) -> bool:
        return bool(self.data["src"]["enabled"])

    @property
    def src_path(self) -> Path:
        return self.root / self.data["src"]["dir"]

    @property
    def src_dataset_slug(self) -> str:
        return self.data["src"]["dataset_slug"]

    @property
    def src_dataset_id(self) -> str:
        return f"{self.username}/{self.src_dataset_slug}"

    @property
    def output_path(self) -> Path:
        return self.root / self.data["output"]["dir"]

    @property
    def build_path(self) -> Path:
        return BUILD_DIR / self.name


# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------


def load_dotenv(path: Path = ENV_FILE) -> dict:
    """Parse a simple KEY=VALUE .env file. Missing file yields {}."""
    values: dict = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def credentials() -> tuple[str, str]:
    """Resolve (username, key) from .env, then the environment, then ~/.kaggle.

    Raises ConfigError with setup instructions when nothing usable is found.
    """
    env = load_dotenv()
    username = env.get("KAGGLE_USERNAME") or os.environ.get("KAGGLE_USERNAME")
    key = env.get("KAGGLE_KEY") or os.environ.get("KAGGLE_KEY")

    if not username or not key:
        json_path = Path(
            os.environ.get("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle")
        ) / "kaggle.json"
        if json_path.is_file():
            try:
                blob = json.loads(json_path.read_text(encoding="utf-8"))
                username = username or blob.get("username")
                key = key or blob.get("key")
            except (json.JSONDecodeError, OSError):
                pass

    placeholder = {"your-kaggle-username", "your-kaggle-api-key", ""}
    if not username or not key or username in placeholder or key in placeholder:
        raise ConfigError(
            "Kaggle credentials not found.\n"
            "  1. cp .env.example .env\n"
            "  2. Fill in KAGGLE_USERNAME and KAGGLE_KEY\n"
            "     (kaggle.com -> avatar -> Settings -> API -> Create New Token)\n"
            "  3. make setup"
        )
    return username, key


def kaggle_username() -> str:
    return credentials()[0]


# --------------------------------------------------------------------------
# Project resolution
# --------------------------------------------------------------------------


def list_projects() -> list[str]:
    if not PROJECTS_DIR.is_dir():
        return []
    return sorted(
        p.name
        for p in PROJECTS_DIR.iterdir()
        if p.is_dir() and (p / CONFIG_NAME).is_file()
    )


def active_project() -> str | None:
    if ACTIVE_FILE.is_file():
        name = ACTIVE_FILE.read_text(encoding="utf-8").strip()
        return name or None
    return None


def set_active_project(name: str) -> None:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text(name + "\n", encoding="utf-8")


def resolve_project(name: str | None) -> str:
    """Explicit name -> projects/.active -> the sole project -> error."""
    projects = list_projects()
    if name:
        name = name.strip()
        if name not in projects:
            raise ConfigError(
                f"No project named '{name}'.\n"
                + _choices(projects)
                + "\nCreate one with:  make new P=" + name
            )
        return name

    active = active_project()
    if active and active in projects:
        return active

    if len(projects) == 1:
        return projects[0]

    if not projects:
        raise ConfigError(
            "No projects yet. Create one with:  make new P=my-first-project"
        )
    raise ConfigError(
        "Multiple projects exist and none is active.\n"
        + _choices(projects)
        + "\nPass one explicitly (make push P=<name>) "
        "or set a default (make active P=<name>)."
    )


def _choices(projects: list[str]) -> str:
    if not projects:
        return "  (no projects found under projects/)"
    return "Available projects:\n" + "\n".join(f"  - {p}" for p in projects)


# --------------------------------------------------------------------------
# Load + validate
# --------------------------------------------------------------------------


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load(name: str | None = None, *, require_credentials: bool = True) -> Config:
    """Load and validate a project's configuration."""
    project = resolve_project(name)
    root = PROJECTS_DIR / project
    config_path = root / CONFIG_NAME

    yaml = _yaml()
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path} is not valid YAML:\n{exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path} must contain a YAML mapping.")

    unknown = set(raw) - set(DEFAULTS)
    if unknown:
        raise ConfigError(
            f"{config_path}: unknown top-level key(s): {', '.join(sorted(unknown))}\n"
            f"Valid keys: {', '.join(sorted(DEFAULTS))}"
        )

    data = _deep_merge(DEFAULTS, raw)

    if require_credentials:
        username = kaggle_username()
    else:
        # Offline commands still prefer the real username so their output
        # matches what a push would actually send.
        try:
            username = kaggle_username()
        except ConfigError:
            username = PLACEHOLDER_USERNAME

    # Derived defaults
    if not data["slug"]:
        data["slug"] = project
    if not data["title"]:
        data["title"] = project
    if not data["src"]["dataset_slug"]:
        data["src"]["dataset_slug"] = f"{data['slug']}-src"
    if not data["src"]["dataset_title"]:
        data["src"]["dataset_title"] = f"{data['title']} — source"

    cfg = Config(name=project, root=root, username=username, data=data)
    validate(cfg, config_path)
    return cfg


def validate(cfg: Config, config_path: Path) -> None:
    """Collect every problem, then raise once with the full list."""
    d = cfg.data
    errors: list[str] = []

    def bad(field_name: str, message: str) -> None:
        errors.append(f"  {field_name}: {message}")

    if not isinstance(d["title"], str) or not d["title"].strip():
        bad("title", "must be a non-empty string")

    if not isinstance(d["slug"], str) or not SLUG_RE.match(d["slug"] or ""):
        bad(
            "slug",
            f"'{d['slug']}' is not a valid Kaggle slug "
            "(lowercase letters, digits and single hyphens, e.g. my-ml-run)",
        )
    elif not 3 <= len(d["slug"]) <= 50:
        bad("slug", f"'{d['slug']}' must be 3-50 characters long")

    if d["language"] not in LANGUAGES:
        bad("language", f"'{d['language']}' — expected one of {list(LANGUAGES)}")
    if d["kernel_type"] not in KERNEL_TYPES:
        bad("kernel_type", f"'{d['kernel_type']}' — expected one of {list(KERNEL_TYPES)}")
    if d["accelerator"] not in ACCELERATORS:
        bad(
            "accelerator",
            f"'{d['accelerator']}' — expected one of {list(ACCELERATORS)}. "
            "Kaggle allows GPU or TPU, never both.",
        )

    for key in ("private", "internet"):
        if not isinstance(d[key], bool):
            bad(key, f"must be true or false, got {d[key]!r}")

    # -- sources ---------------------------------------------------------
    src_specs = (
        ("sources.datasets", d["sources"]["datasets"], OWNER_SLUG_RE, "owner/dataset-slug"),
        ("sources.competitions", d["sources"]["competitions"], COMPETITION_RE, "competition-slug"),
        ("sources.kernels", d["sources"]["kernels"], OWNER_SLUG_RE, "owner/kernel-slug"),
        ("sources.models", d["sources"]["models"], MODEL_RE, "owner/model/framework/variation/version"),
    )
    for label, values, pattern, shape in src_specs:
        if values is None:
            d_key, sub = label.split(".")
            d[d_key][sub] = values = []
        if not isinstance(values, list):
            bad(label, "must be a list of slugs")
            continue
        for item in values:
            if not isinstance(item, str) or not pattern.match(item.strip()):
                bad(label, f"'{item}' is not of the form {shape}")

    # -- src bundle ------------------------------------------------------
    s = d["src"]
    for key in ("enabled", "include_shared", "inject_bootstrap"):
        if not isinstance(s[key], bool):
            bad(f"src.{key}", f"must be true or false, got {s[key]!r}")
    if s["enabled"]:
        if not SLUG_RE.match(s["dataset_slug"] or ""):
            bad("src.dataset_slug", f"'{s['dataset_slug']}' is not a valid Kaggle slug")
        if not 6 <= len(str(s["dataset_title"])) <= 50:
            bad(
                "src.dataset_title",
                f"'{s['dataset_title']}' must be 6-50 characters (Kaggle's limit)",
            )
        if not cfg.src_path.is_dir():
            bad(
                "src.dir",
                f"'{s['dir']}' does not exist at {cfg.src_path}. "
                "Create it, or set src.enabled: false",
            )
        if s["include_shared"] and not SHARED_DIR.is_dir():
            bad("src.include_shared", f"is true but {SHARED_DIR} does not exist")

    # -- push ------------------------------------------------------------
    p = d["push"]
    if not isinstance(p["wait"], bool):
        bad("push.wait", f"must be true or false, got {p['wait']!r}")
    if not isinstance(p["poll_interval"], int) or p["poll_interval"] < 1:
        bad("push.poll_interval", "must be a positive integer (seconds)")
    if p["timeout"] is not None and (
        not isinstance(p["timeout"], int) or p["timeout"] < 1
    ):
        bad("push.timeout", "must be null or a positive integer (seconds)")

    # -- notebook --------------------------------------------------------
    nb = cfg.notebook_path
    if not nb.is_file():
        bad("notebook", f"file not found: {nb}")
    elif d["kernel_type"] == "notebook" and nb.suffix == ".ipynb":
        try:
            blob = json.loads(nb.read_text(encoding="utf-8"))
            if "cells" not in blob:
                bad("notebook", f"{nb} is JSON but has no 'cells' key — not a notebook")
        except json.JSONDecodeError as exc:
            bad("notebook", f"{nb} is not valid notebook JSON: {exc}")

    if errors:
        raise ConfigError(
            f"{config_path} has {len(errors)} problem(s):\n" + "\n".join(errors)
        )
