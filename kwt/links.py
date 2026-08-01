"""Turn a pasted Kaggle URL into the slug its metadata needs.

Users copy links out of the address bar; Kaggle's metadata wants bare slugs.
This module does that translation for every kind of source a notebook can
attach, so nobody has to know the difference.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# config.yml key  ->  the kernel-metadata.json field it feeds
KINDS = {
    "datasets": "dataset_sources",
    "competitions": "competition_sources",
    "kernels": "kernel_sources",
    "models": "model_sources",
}


class LinkError(Exception):
    """The pasted link is not a Kaggle source we can attach."""


def _segments(text: str) -> list[str]:
    """Path segments of a URL, or of a bare `owner/slug` string."""
    text = text.strip().strip("<>").strip('"').strip("'")
    if "://" in text or text.startswith("www."):
        if text.startswith("www."):
            text = "https://" + text
        parsed = urlparse(text)
        if parsed.netloc and "kaggle.com" not in parsed.netloc.lower():
            raise LinkError(f"'{parsed.netloc}' is not a kaggle.com link.")
        path = parsed.path
    else:
        path = text
    return [seg for seg in path.split("/") if seg]


def parse(text: str) -> tuple[str, str]:
    """Return (config.yml key, slug) for a link or bare slug.

    >>> parse("https://www.kaggle.com/datasets/zillow/zecon")
    ('datasets', 'zillow/zecon')
    >>> parse("https://www.kaggle.com/c/titanic")
    ('competitions', 'titanic')
    """
    segments = _segments(text)
    if not segments:
        raise LinkError(f"Could not read a Kaggle source from '{text}'.")

    head = segments[0].lower()
    rest = segments[1:]

    if head in ("datasets", "dataset", "d"):
        if len(rest) < 2:
            raise LinkError(
                f"Dataset link is missing the owner or name: '{text}'\n"
                "Expected .../datasets/<owner>/<dataset-name>"
            )
        return "datasets", f"{rest[0]}/{rest[1]}"

    if head in ("competitions", "competition", "c"):
        if not rest:
            raise LinkError(f"Competition link is missing its name: '{text}'")
        return "competitions", rest[0]

    if head in ("code", "kernels", "kernel"):
        if len(rest) < 2:
            raise LinkError(
                f"Notebook link is missing the owner or name: '{text}'\n"
                "Expected .../code/<owner>/<notebook-name>"
            )
        return "kernels", f"{rest[0]}/{rest[1]}"

    if head in ("models", "model", "m"):
        if len(rest) < 5:
            raise LinkError(
                f"Model links need all five parts: '{text}'\n"
                "Expected .../models/<owner>/<model>/<framework>/<variation>/<version>"
            )
        return "models", "/".join(rest[:5])

    # Bare "owner/slug" (or the legacy kaggle.com/<owner>/<dataset> form).
    if len(segments) >= 2 and re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", segments[0]):
        return "datasets", f"{segments[0]}/{segments[1]}"

    raise LinkError(
        f"Could not tell what kind of Kaggle source '{text}' is.\n"
        "Supported:\n"
        "  https://www.kaggle.com/datasets/<owner>/<name>\n"
        "  https://www.kaggle.com/competitions/<name>\n"
        "  https://www.kaggle.com/code/<owner>/<name>\n"
        "  https://www.kaggle.com/models/<owner>/<model>/<fw>/<variation>/<version>\n"
        "  or a bare slug: <owner>/<name>"
    )


def mount_hint(kind: str, slug: str) -> str:
    """Where the attached source shows up inside the notebook."""
    name = slug.split("/")[-1]
    if kind == "datasets":
        return f"/kaggle/input/datasets/{slug}  (use find_input('{name}'))"
    if kind == "competitions":
        return f"/kaggle/input/{slug}  (use find_input('{name}'))"
    if kind == "kernels":
        return f"the output of {slug}, under /kaggle/input"
    return f"/kaggle/input/{slug.split('/')[1]}  (Kaggle Models)"
