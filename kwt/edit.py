"""Edit config.yml in place without destroying its comments.

Round-tripping through yaml.safe_load/dump would strip every comment in the
file, and those comments are most of what makes config.yml approachable. So we
patch the text directly instead.
"""

from __future__ import annotations

import re
from pathlib import Path

ITEM_RE = re.compile(r"^\s*-\s*(.+?)\s*$")


class EditError(Exception):
    """The config file is not in a shape we can safely patch."""


def _quoted(value: str) -> str:
    return f'"{value}"'


def _unquote(value: str) -> str:
    return value.strip().strip('"').strip("'")


def _find_block(lines: list[str], key: str) -> tuple[int, int] | None:
    """Line range [start, end) of a top-level `key:` block, header included."""
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}\s*:", line):
            end = index + 1
            while end < len(lines):
                stripped = lines[end]
                if stripped.strip() and not stripped.startswith((" ", "\t")):
                    break
                end += 1
            return index, end
    return None


def _find_key_line(lines: list[str], start: int, end: int, key: str) -> int | None:
    for index in range(start, end):
        if re.match(rf"^\s+{re.escape(key)}\s*:", lines[index]):
            return index
    return None


def list_items(path: Path, kind: str) -> list[str]:
    """Current entries of `sources.<kind>`."""
    lines = path.read_text(encoding="utf-8").splitlines()
    block = _find_block(lines, "sources")
    if not block:
        return []
    key_line = _find_key_line(lines, *block, key=kind)
    if key_line is None:
        return []

    _, value = lines[key_line].split(":", 1)
    value = value.split("#", 1)[0].strip()
    if value.startswith("["):
        inner = value.strip("[]").strip()
        return [_unquote(v) for v in inner.split(",") if v.strip()] if inner else []

    items = []
    for index in range(key_line + 1, block[1]):
        line = lines[index]
        if line.strip().startswith("#") or not line.strip():
            continue
        match = ITEM_RE.match(line)
        if not match:
            break
        items.append(_unquote(match.group(1).split("#", 1)[0]))
    return items


def add_source(path: Path, kind: str, slug: str) -> bool:
    """Append `slug` to `sources.<kind>`. False if it was already there."""
    existing = list_items(path, kind)
    if slug in existing:
        return False

    lines = path.read_text(encoding="utf-8").splitlines()
    block = _find_block(lines, "sources")

    # No `sources:` block at all — append a whole one.
    if block is None:
        lines += ["", "sources:", f"  {kind}:", f"    - {_quoted(slug)}"]
        return _save(path, lines)

    key_line = _find_key_line(lines, *block, key=kind)

    # `sources:` exists but not this kind of source.
    if key_line is None:
        lines[block[1] : block[1]] = [f"  {kind}:", f"    - {_quoted(slug)}"]
        return _save(path, lines)

    head, raw = lines[key_line].split(":", 1)
    value, comment = _split_comment(raw)

    if value.startswith("[") or value == "":
        # Flow style (`[]` or `["a"]`) or an empty header: rewrite as a block
        # list so future additions are one clean line each. The trailing
        # comment moves up to the key so its guidance survives.
        replacement = [f"{head}:{comment}"] + [
            f"    - {_quoted(item)}" for item in [*existing, slug]
        ]
        end_of_list = key_line + 1
        while end_of_list < block[1] and ITEM_RE.match(lines[end_of_list]):
            end_of_list += 1
        lines[key_line:end_of_list] = replacement
        return _save(path, lines)

    raise EditError(
        f"Cannot patch `sources.{kind}` automatically — the value on line "
        f"{key_line + 1} is not a list. Add '{slug}' by hand instead."
    )


def _split_comment(raw: str) -> tuple[str, str]:
    """Split `  []        # note` into ("[]", "        # note").

    The comment keeps its original padding so rewriting a line does not break
    the column alignment of the comments around it.
    """
    if "#" in raw:
        value, comment = raw.split("#", 1)
        padding = value[len(value.rstrip()) :] or "  "
        return value.strip(), f"{padding}#{comment.rstrip()}"
    return raw.strip(), ""


def _save(path: Path, lines: list[str]) -> bool:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def remove_source(path: Path, kind: str, slug: str) -> bool:
    """Drop `slug` from `sources.<kind>`. False if it wasn't there."""
    if slug not in list_items(path, kind):
        return False

    lines = path.read_text(encoding="utf-8").splitlines()
    block = _find_block(lines, "sources")
    key_line = _find_key_line(lines, *block, key=kind) if block else None
    if key_line is None:
        return False

    for index in range(key_line + 1, block[1]):
        match = ITEM_RE.match(lines[index])
        if match and _unquote(match.group(1).split("#", 1)[0]) == slug:
            del lines[index]
            # Emptying a block list would leave a bare `key:` (which YAML reads
            # as null); put the explicit empty list back.
            if not ITEM_RE.match(lines[key_line + 1] if key_line + 1 < len(lines) else ""):
                head, raw = lines[key_line].split(":", 1)
                _, comment = _split_comment(raw)
                lines[key_line] = f"{head}: []{comment}"
            return _save(path, lines)

    # Flow style: rewrite the single line without the removed entry.
    remaining = [item for item in list_items(path, kind) if item != slug]
    head = lines[key_line].split(":", 1)[0]
    rendered = ", ".join(_quoted(item) for item in remaining)
    lines[key_line] = f"{head}: [{rendered}]"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True
