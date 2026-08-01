"""Example module — runs locally *and* inside the Kaggle notebook.

`make push` uploads this folder as a private Kaggle dataset and the notebook's
bootstrap cell puts it on sys.path, so `from example_lib import describe` works
in both places.
"""

from __future__ import annotations


def describe(name: str = "world") -> str:
    """Trivial placeholder so the round-trip is easy to verify."""
    return f"Hello from example_lib, {name}!"
