"""Subprocess wrapper around the `kaggle` CLI.

Centralises three annoyances: finding the executable, filtering the urllib3 /
LibreSSL warnings the CLI prints on stderr under some Python builds, and
turning non-zero exits into an exception that carries Kaggle's own message.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .config import credentials

NOISE_MARKERS = (
    "NotOpenSSLWarning",
    "urllib3 v2 only supports OpenSSL",
    "warnings.warn(",
    "Warning: Your Kaggle API key is readable by other users",
    "Looking for a faster way",
)


class KaggleError(Exception):
    """A `kaggle` invocation failed; the message is the CLI's own output."""


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def text(self) -> str:
        return "\n".join(part for part in (self.stdout, self.stderr) if part).strip()


def _executable() -> str:
    """Find the `kaggle` CLI, preferring the one beside this interpreter.

    A venv's bin/ is not on PATH unless it has been activated, and a stale
    `kaggle` from some other Python often is. Checking next to sys.executable
    first keeps the CLI and its library in the same environment.
    """
    sibling = Path(sys.executable).parent / "kaggle"
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return str(sibling)

    exe = shutil.which("kaggle")
    if exe:
        return exe

    raise KaggleError(
        "The `kaggle` CLI is not installed in this environment.\n"
        "Run `make setup`, or install it directly: pip install kaggle"
    )


def _clean(stream: str) -> str:
    lines = [
        line
        for line in (stream or "").splitlines()
        if not any(marker in line for marker in NOISE_MARKERS)
    ]
    return "\n".join(lines).strip()


def _env() -> dict:
    """Inject credentials so the CLI works even without ~/.kaggle/kaggle.json."""
    env = os.environ.copy()
    try:
        username, key = credentials()
        env["KAGGLE_USERNAME"] = username
        env["KAGGLE_KEY"] = key
    except Exception:
        # Let the CLI produce its own auth error rather than masking it here.
        pass
    return env


def run(*args: str, check: bool = True, echo: bool = False) -> Result:
    """Run `kaggle <args>` and return a cleaned Result."""
    cmd = [_executable(), *args]
    if echo:
        print(f"$ kaggle {' '.join(args)}", file=sys.stderr)

    proc = subprocess.run(cmd, capture_output=True, text=True, env=_env())
    result = Result(proc.returncode, _clean(proc.stdout), _clean(proc.stderr))

    if check and not result.ok:
        raise KaggleError(result.text or f"`kaggle {' '.join(args)}` failed.")
    return result


def whoami() -> str:
    """Verify credentials with a cheap authenticated call; return the username."""
    username, _ = credentials()
    result = run("kernels", "list", "--mine", "--page-size", "1", check=False)
    if not result.ok:
        raise KaggleError(
            "Kaggle rejected your credentials.\n"
            f"{result.text}\n\n"
            "Check KAGGLE_USERNAME / KAGGLE_KEY in .env, or generate a fresh "
            "token at kaggle.com -> Settings -> API -> Create New Token."
        )
    return username


def poll(fetch, is_done, *, interval: int = 15, timeout: int | None = None,
         on_tick=None):
    """Call `fetch()` every `interval` seconds until `is_done(value)` is true.

    Returns the final value, or the last seen value if `timeout` elapses.
    """
    started = time.monotonic()
    while True:
        value = fetch()
        if on_tick:
            on_tick(value)
        if is_done(value):
            return value
        if timeout is not None and time.monotonic() - started >= timeout:
            return value
        time.sleep(interval)
