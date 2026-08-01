"""kwt command line entry point.

Usually invoked through the Makefile (`make push P=my-project`), but works
directly too: `python -m kwt push my-project`.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from . import (
    __version__,
    config,
    edit,
    kaggle_cli,
    links,
    metadata,
    notebook,
    scaffold,
    srcsync,
)
from .config import BUILD_DIR, CONFIG_NAME, PROJECTS_DIR, REPO_ROOT, Config, ConfigError

DONE_STATES = ("complete", "error", "cancel")


# --------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------


def say(message: str = "") -> None:
    print(message, flush=True)


def step(message: str) -> None:
    print(f"==> {message}", flush=True)


def fail(message: str) -> None:
    print(f"\nError: {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------


def _interactive(args: argparse.Namespace) -> bool:
    """Only prompt when a human is actually there to answer."""
    return not args.no_input and sys.stdin.isatty()


def _ask(question: str, *, secret: bool = False, default: str = "") -> str:
    try:
        answer = getpass.getpass(question) if secret else input(question)
    except EOFError:
        return default
    return answer.strip() or default


def _ask_credentials() -> tuple[str, str]:
    """Prompt for a username and key, accepting a pasted kaggle.json too."""
    say("    Get them at kaggle.com -> Settings -> API -> Create New Token.")
    say("    Tip: you can paste the whole contents of kaggle.json below.")
    say()

    while True:
        first = _ask("    Kaggle username (or paste kaggle.json): ")
        if not first:
            say("    A username is required.\n")
            continue

        # Pasted the downloaded token file rather than typing the fields.
        if first.startswith("{"):
            try:
                blob = json.loads(first)
                username, key = blob["username"].strip(), blob["key"].strip()
            except (json.JSONDecodeError, KeyError, AttributeError):
                say("    That looked like JSON but had no username/key in it.\n")
                continue
            say(f"    read username '{username}' and key from the pasted JSON")
            return username, key

        key = _ask("    Kaggle API key (hidden): ", secret=True)
        if not key:
            say("    A key is required.\n")
            continue
        if len(key) < 20:
            say(f"    That key is only {len(key)} characters — Kaggle's are 32.")
            if not _ask("    Use it anyway? [y/N]: ").lower().startswith("y"):
                say()
                continue
        return first, key


def _write_env(username: str, key: str) -> Path:
    """Persist credentials to .env so setup only has to ask once."""
    path = config.ENV_FILE
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []

    updated = {"KAGGLE_USERNAME": False, "KAGGLE_KEY": False}
    values = {"KAGGLE_USERNAME": username, "KAGGLE_KEY": key}
    for index, line in enumerate(lines):
        for name in values:
            if re.match(rf"^\s*{name}\s*=", line):
                lines[index] = f"{name}={values[name]}"
                updated[name] = True

    if not any(updated.values()) and not lines:
        lines = ["# Kaggle credentials. This file is gitignored — never commit it."]
    for name, done in updated.items():
        if not done:
            lines.append(f"{name}={values[name]}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass  # Windows and some filesystems don't support this; harmless.
    return path


def cmd_setup(args: argparse.Namespace) -> None:
    step("Installing Python dependencies")
    requirements = REPO_ROOT / "requirements.txt"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements)]
    )
    if result.returncode != 0:
        fail("pip install failed. Check the output above.")
    say("    dependencies installed")

    step("Kaggle credentials")
    have: tuple[str, str] | None = None
    try:
        have = config.credentials()
    except ConfigError:
        have = None

    if have and not args.reconfigure:
        say(f"    using the credentials already configured for '{have[0]}'")
        say("    (run `make setup RECONFIGURE=1` to enter different ones)")
        username, key = have
    elif _interactive(args):
        username, key = _ask_credentials()
        env_path = _write_env(username, key)
        say(f"    wrote {env_path.relative_to(REPO_ROOT)}")
    else:
        fail(
            "No Kaggle credentials found and nothing to prompt with.\n"
            "  cp .env.example .env, fill in KAGGLE_USERNAME and KAGGLE_KEY,\n"
            "  then run `make setup` again."
        )

    config_dir = Path(os.environ.get("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle"))
    config_dir.mkdir(parents=True, exist_ok=True)
    token = config_dir / "kaggle.json"
    token.write_text(json.dumps({"username": username, "key": key}), encoding="utf-8")
    try:
        token.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600 — the CLI warns otherwise
    except OSError:
        pass
    say(f"    wrote {token}")

    step("Verifying credentials against Kaggle")
    try:
        who = kaggle_cli.whoami()
    except kaggle_cli.KaggleError as exc:
        fail(str(exc))
    say(f"    authenticated as {who}")

    created = _setup_first_project(args)

    projects = config.list_projects()
    say()
    say("Setup complete.")
    say()

    target = created or (projects[0] if projects else None)
    if target is None:
        say("Next:")
        say("  1. Create a project   make new P=my-first-project")
        return

    if not created and projects:
        say("Projects: " + ", ".join(projects))
        say()
    say("Next:")
    say(f'  1. Attach data    make add P={target} URL="<paste a Kaggle dataset link>"')
    say(f"  2. Write code     projects/{target}/notebook.ipynb  (helpers in src/)")
    say(f"  3. Run on Kaggle  make push P={target}")
    say(f"  4. Get results    make output P={target}")


def _setup_first_project(args: argparse.Namespace) -> str | None:
    """Offer to scaffold a project as the last step of setup."""
    if args.project:
        wanted = args.project
    elif _interactive(args):
        step("First project")
        existing = config.list_projects()
        if existing:
            say("    You already have: " + ", ".join(existing))
        wanted = _ask("    Name for a new project (blank to skip): ")
    else:
        return None

    if not wanted:
        return None

    try:
        scaffold.create(wanted)
    except ConfigError as exc:
        # A bad name here shouldn't undo a successful credential setup.
        say(f"    skipped: {exc}")
        return None

    say(f"    created projects/{wanted}/")
    return wanted


# --------------------------------------------------------------------------
# new / active / list
# --------------------------------------------------------------------------


def cmd_new(args: argparse.Namespace) -> None:
    root = scaffold.create(args.name, activate=args.activate)
    step(f"Created {root.relative_to(REPO_ROOT)}")
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            say(f"    {path.relative_to(REPO_ROOT)}")
    say()
    say(f"Edit projects/{args.name}/config.yml, then:  make push P={args.name}")
    if config.active_project() == args.name:
        say(f"'{args.name}' is now the default project (projects/.active).")


def cmd_active(args: argparse.Namespace) -> None:
    if args.name:
        name = config.resolve_project(args.name)
        config.set_active_project(name)
        say(f"Default project is now '{name}'.")
    else:
        current = config.active_project()
        say(current or "(no default project set)")


def cmd_list(args: argparse.Namespace) -> None:
    projects = config.list_projects()
    active = config.active_project()

    step("Local projects")
    if not projects:
        say("    (none yet — make new P=my-first-project)")
    for name in projects:
        marker = "*" if name == active else " "
        try:
            cfg = config.load(name, require_credentials=False)
            detail = f"{cfg.slug}  [{cfg['accelerator']}]"
            detail += "  private" if cfg["private"] else "  public"
        except ConfigError:
            detail = "(invalid config — run `make validate P=%s`)" % name
        say(f"  {marker} {name:<24} {detail}")
    if active:
        say("\n  * = default project used when P= is omitted")

    if args.remote:
        step("Your notebooks on Kaggle")
        result = kaggle_cli.run("kernels", "list", "--mine", check=False)
        say(result.text or "    (none)")


# --------------------------------------------------------------------------
# add / rm — attach data by pasting its Kaggle link
# --------------------------------------------------------------------------


def _config_path(project: str | None) -> tuple[str, Path]:
    name = config.resolve_project(project)
    return name, PROJECTS_DIR / name / CONFIG_NAME


def _expand(raw_args: list[str]) -> list[str]:
    """Split each argument on whitespace and commas.

    The Makefile passes URL="..." as a single quoted argument — quoting is what
    stops a `?select=a&b=c` query string from being mangled by the shell — so
    several links arrive glued together. Splitting here keeps both working.
    """
    items: list[str] = []
    for raw in raw_args:
        items.extend(part for part in re.split(r"[\s,]+", raw.strip()) if part)
    return items


def cmd_add(args: argparse.Namespace) -> None:
    name, path = _config_path(args.project)
    added: list[tuple[str, str]] = []

    urls = _expand(args.urls)
    if not urls:
        fail('No link given. Try: make add URL="https://www.kaggle.com/datasets/owner/name"')

    for raw in urls:
        try:
            kind, slug = links.parse(raw)
        except links.LinkError as exc:
            fail(str(exc))

        if edit.add_source(path, kind, slug):
            say(f"  + {kind[:-1]}: {slug}")
            added.append((kind, slug))
        else:
            say(f"  = already attached: {slug}")

    if not added:
        return

    # Re-load so a malformed edit is caught here rather than at push time.
    cfg = config.load(name, require_credentials=False)
    step(f"projects/{name}/config.yml updated")
    for kind, slug in added:
        say(f"    {slug}  ->  {links.mount_hint(kind, slug)}")
    say()
    say(f"It attaches on the next push:  make push P={name}")
    if any(kind == "competitions" for kind, _ in added):
        say("Accept the competition's rules on its Kaggle page first, "
            "or the run will fail with 403.")
    del cfg


def _resolve_attached(path: Path, raw: str) -> tuple[str, str]:
    """Match `raw` against what is already attached, before parsing it as a link.

    Lets you detach with the short name you see in `make sources` — a bare
    'titanic' is ambiguous as a link but unambiguous as an attached source.
    """
    token = raw.strip().strip("/")
    matches = [
        (kind, slug)
        for kind in links.KINDS
        for slug in edit.list_items(path, kind)
        if slug == token or slug.split("/")[-1] == token
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        listed = "\n".join(f"  - {slug}  ({kind})" for kind, slug in matches)
        raise ConfigError(f"'{raw}' matches more than one attached source:\n{listed}")
    return links.parse(raw)


def cmd_rm(args: argparse.Namespace) -> None:
    name, path = _config_path(args.project)
    for raw in _expand(args.urls):
        try:
            kind, slug = _resolve_attached(path, raw)
        except links.LinkError as exc:
            fail(str(exc))
        if edit.remove_source(path, kind, slug):
            say(f"  - {kind[:-1]}: {slug}")
        else:
            say(f"  ? not attached: {slug}")
    config.load(name, require_credentials=False)
    step(f"projects/{name}/config.yml updated")


def cmd_sources(args: argparse.Namespace) -> None:
    name, path = _config_path(args.project)
    step(f"Attached to '{name}'")
    empty = True
    for kind in links.KINDS:
        items = edit.list_items(path, kind)
        if not items:
            continue
        empty = False
        say(f"  {kind}:")
        for slug in items:
            say(f"    - {slug}")
    cfg = config.load(name, require_credentials=False)
    if cfg.src_enabled:
        empty = False
        say(f"  your code (automatic):\n    - {cfg.src_dataset_id}")
    if empty:
        say("  (nothing yet — make add P=%s URL=<kaggle link>)" % name)


# --------------------------------------------------------------------------
# validate
# --------------------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> None:
    cfg = config.load(args.project, require_credentials=False)
    step(f"Project '{cfg.name}' is valid")
    payload = metadata.kernel_metadata(cfg)
    say(json.dumps(payload, indent=2))
    if cfg.username == config.PLACEHOLDER_USERNAME:
        say("\nNote: credentials are not configured yet, so `id` is a placeholder.")
        say("Run `make setup` before pushing.")


# --------------------------------------------------------------------------
# push
# --------------------------------------------------------------------------


def build(cfg: Config, *, quiet: bool = False) -> Path:
    """Stage everything Kaggle needs into .build/<project>/."""
    if cfg.build_path.exists():
        shutil.rmtree(cfg.build_path)
    cfg.build_path.mkdir(parents=True)

    code_file = notebook.stage(cfg)
    metadata.write(metadata.kernel_metadata(cfg), cfg.build_path / "kernel-metadata.json")
    if not quiet:
        say(f"    staged {code_file.name} + kernel-metadata.json")
    return cfg.build_path


def cmd_push(args: argparse.Namespace) -> None:
    cfg = config.load(args.project)
    step(f"Pushing '{cfg.name}' as {cfg.kernel_id}")

    if cfg.src_enabled:
        step("Syncing src/ to a private Kaggle dataset")
        srcsync.sync(cfg, message=args.message)
    else:
        say("    src sync disabled for this project")

    step("Building upload folder")
    # The src dataset must exist before kernel-metadata.json references it,
    # which is why the sync above runs first.
    folder = build(cfg)

    step("Uploading notebook")
    push_args = ["kernels", "push", "-p", str(folder)]
    timeout = args.timeout if args.timeout is not None else cfg["push"]["timeout"]
    if timeout:
        push_args += ["-t", str(timeout)]
    result = kaggle_cli.run(*push_args, check=False)
    if not result.ok:
        fail(result.text)
    say(f"    {result.text}")

    say()
    say(f"Kernel:  {cfg.kernel_url}")

    if args.wait or cfg["push"]["wait"]:
        step("Waiting for the run to finish")
        final = _wait_for_run(cfg)
        say()
        say(f"Final status: {final}")
        if "complete" in final.lower():
            say(f"Fetch results with:  make output P={cfg.name}")
        else:
            fail(f"Run did not complete cleanly ({final}). Open {cfg.kernel_url}")
    else:
        say(f"Check progress:  make status P={cfg.name}")


def _wait_for_run(cfg: Config) -> str:
    seen: list[str] = []

    def fetch() -> str:
        result = kaggle_cli.run("kernels", "status", cfg.kernel_id, check=False)
        return (result.text or "unknown").strip()

    def done(text: str) -> bool:
        return any(state in text.lower() for state in DONE_STATES)

    def tick(text: str) -> None:
        if text not in seen:
            seen.append(text)
            say(f"    {text}")

    return kaggle_cli.poll(
        fetch,
        done,
        interval=cfg["push"]["poll_interval"],
        timeout=cfg["push"]["timeout"],
        on_tick=tick,
    )


# --------------------------------------------------------------------------
# status / output / pull
# --------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> None:
    cfg = config.load(args.project)
    if args.watch:
        step(f"Watching {cfg.kernel_id}")
        say(_wait_for_run(cfg))
        return
    result = kaggle_cli.run("kernels", "status", cfg.kernel_id, check=False)
    say(result.text or "unknown")
    say(cfg.kernel_url)


def cmd_output(args: argparse.Namespace) -> None:
    cfg = config.load(args.project)
    destination = cfg.output_path
    destination.mkdir(parents=True, exist_ok=True)

    step(f"Downloading output of {cfg.kernel_id}")
    result = kaggle_cli.run(
        "kernels", "output", cfg.kernel_id, "-p", str(destination), "-o", check=False
    )
    if not result.ok:
        fail(
            result.text
            + "\n\nHas the run finished? Check with:  make status P=" + cfg.name
        )
    say(result.text)

    files = sorted(p for p in destination.rglob("*") if p.is_file())
    step(f"{len(files)} file(s) in {destination.relative_to(REPO_ROOT)}/")
    for path in files:
        size = path.stat().st_size
        say(f"    {path.relative_to(destination)}  ({_human(size)})")


def cmd_pull(args: argparse.Namespace) -> None:
    cfg = config.load(args.project)
    target = cfg.notebook_path
    if target.exists() and not args.force:
        fail(
            f"{target.relative_to(REPO_ROOT)} already exists.\n"
            "Pulling would overwrite your local edits. Re-run with --force "
            f"(make pull P={cfg.name} FORCE=1) if that is what you want."
        )

    staging = cfg.build_path / "_pull"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    step(f"Pulling {cfg.kernel_id}")
    result = kaggle_cli.run(
        "kernels", "pull", cfg.kernel_id, "-p", str(staging), check=False
    )
    if not result.ok:
        fail(result.text)

    pulled = [p for p in staging.iterdir() if p.suffix in (".ipynb", ".py", ".R", ".Rmd")]
    if not pulled:
        fail(f"Kaggle returned no code file for {cfg.kernel_id}.")

    source = pulled[0]
    stripped = 0
    if source.suffix == ".ipynb":
        # The uploaded copy carries the injected bootstrap cell; drop it so the
        # tracked notebook stays exactly as clean as it was before the push.
        blob, stripped = notebook.strip_bootstrap(notebook.read_notebook(source))
        target.write_text(json.dumps(blob, indent=1) + "\n", encoding="utf-8")
    else:
        shutil.copyfile(source, target)

    say(f"    wrote {target.relative_to(REPO_ROOT)}")
    if stripped:
        say(f"    stripped {stripped} auto-generated bootstrap cell(s)")


# --------------------------------------------------------------------------
# clean
# --------------------------------------------------------------------------


def cmd_clean(args: argparse.Namespace) -> None:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
        say(f"Removed {BUILD_DIR.relative_to(REPO_ROOT)}/")
    else:
        say("Nothing to clean.")

    if args.outputs:
        for name in config.list_projects():
            outputs = config.PROJECTS_DIR / name / "outputs"
            if not outputs.is_dir():
                continue
            for path in outputs.iterdir():
                if path.name == ".gitkeep":
                    continue
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            say(f"Emptied {outputs.relative_to(REPO_ROOT)}/")


def _human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size}B"


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kwt",
        description="Drive Kaggle notebooks from this repo.",
    )
    parser.add_argument("--version", action="version", version=f"kwt {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def with_project(p):
        p.add_argument(
            "project",
            nargs="?",
            default=None,
            help="project name (defaults to projects/.active)",
        )
        return p

    s = sub.add_parser("setup", help="install deps, write credentials, verify them")
    s.add_argument(
        "--reconfigure",
        action="store_true",
        help="ask for credentials again even if some are already configured",
    )
    s.add_argument(
        "--project", default=None, help="also scaffold this project, without asking"
    )
    s.add_argument(
        "--no-input", action="store_true", help="never prompt (for scripts and CI)"
    )
    s.set_defaults(func=cmd_setup)

    s = sub.add_parser("new", help="scaffold a new project folder")
    s.add_argument("name")
    s.add_argument(
        "--activate",
        action="store_true",
        default=None,
        help="make this the default project",
    )
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("active", help="show or set the default project")
    s.add_argument("name", nargs="?", default=None)
    s.set_defaults(func=cmd_active)

    s = sub.add_parser("list", help="list local projects (and optionally remote ones)")
    s.add_argument("--remote", action="store_true", help="also list your Kaggle kernels")
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("add", help="attach a dataset/competition by pasting its link")
    s.add_argument("urls", nargs="+", metavar="URL")
    s.add_argument("-p", "--project", default=None)
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("rm", help="detach a source by link or slug")
    s.add_argument("urls", nargs="+", metavar="URL")
    s.add_argument("-p", "--project", default=None)
    s.set_defaults(func=cmd_rm)

    s = with_project(sub.add_parser("sources", help="list what this project attaches"))
    s.set_defaults(func=cmd_sources)

    s = with_project(sub.add_parser("validate", help="check config offline"))
    s.set_defaults(func=cmd_validate)

    s = with_project(sub.add_parser("push", help="sync src, upload, and run"))
    s.add_argument("--wait", action="store_true", help="block until the run finishes")
    s.add_argument("-m", "--message", default=None, help="src dataset version note")
    s.add_argument("--timeout", type=int, default=None, help="cap run length (seconds)")
    s.set_defaults(func=cmd_push)

    s = with_project(sub.add_parser("status", help="show the latest run's status"))
    s.add_argument("--watch", action="store_true", help="poll until the run finishes")
    s.set_defaults(func=cmd_status)

    s = with_project(sub.add_parser("output", help="download run outputs"))
    s.set_defaults(func=cmd_output)

    s = with_project(sub.add_parser("pull", help="pull the notebook back from Kaggle"))
    s.add_argument("--force", action="store_true", help="overwrite the local notebook")
    s.set_defaults(func=cmd_pull)

    s = sub.add_parser("clean", help="remove .build/")
    s.add_argument("--outputs", action="store_true", help="also empty outputs/ folders")
    s.set_defaults(func=cmd_clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ConfigError as exc:
        fail(str(exc))
    except kaggle_cli.KaggleError as exc:
        fail(str(exc))
    except KeyboardInterrupt:
        say("\nInterrupted.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
