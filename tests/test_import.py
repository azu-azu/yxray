"""Smoke test: package is importable."""


def test_package_importable() -> None:
    """Verify that yxray is importable and has a version string."""
    import yxray

    assert yxray.__version__ == "0.1.0"
