"""Template loading helpers for bundled renderer assets."""

from __future__ import annotations

import importlib.resources as pkg_resources
import pathlib


def load_template(name: str) -> str:
    """Load a bundled template by filename."""
    try:
        return (
            pkg_resources.files("yxray.templates")
            .joinpath(name)
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        path = pathlib.Path(__file__).parent.parent / "templates" / name
        return path.read_text(encoding="utf-8")
