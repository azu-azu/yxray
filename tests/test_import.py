"""Smoke test: package is importable."""


def test_package_importable() -> None:
    """Verify that alteryx_git_companion is importable and has a version string."""
    import alteryx_git_companion

    assert alteryx_git_companion.__version__ == "0.1.0"
