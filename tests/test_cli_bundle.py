"""Smoke test that acd CLI package is importable — confirms bundling works."""

from __future__ import annotations


def test_cli_bundle_importable():
    """Confirms acd CLI package is importable — required for PyInstaller bundling."""
    from alteryx_diff.pipeline.pipeline import run  # noqa: F401

    assert callable(run)
