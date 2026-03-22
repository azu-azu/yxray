"""Failing test stubs for Phase 15 tray state computation.

Tests _compute_state() from app.tray.
app.tray does not exist yet -- tests are in RED state.
They will be driven GREEN in Plan 03.

_compute_state is a pure function: dict -> (state_str, tooltip_str).
No pystray or OS dependency required.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Graceful RED: wrap import so tests report FAILED not collection ERROR
# ---------------------------------------------------------------------------

try:
    from app.tray import _compute_state
except ImportError:
    _compute_state = None  # type: ignore[assignment]


def _require():
    """Fail clearly if _compute_state not yet implemented."""
    if _compute_state is None:
        pytest.fail("app.tray._compute_state not implemented yet")


# ---------------------------------------------------------------------------
# test_state_changes_detected
# ---------------------------------------------------------------------------


def test_state_changes_detected():
    """Single project with 3 changes -> ("changes", "... 3 changes detected")."""
    _require()

    status_data = {"proj1": {"changed_count": 3}}
    state, tooltip = _compute_state(status_data)

    assert state == "changes", f"Expected state 'changes', got {state!r}"
    assert "3 changes detected" in tooltip, (
        f"Expected '3 changes detected' in tooltip, got {tooltip!r}"
    )
    assert "Alteryx Git Companion" in tooltip, (
        f"Expected app name in tooltip, got {tooltip!r}"
    )


# ---------------------------------------------------------------------------
# test_state_watching
# ---------------------------------------------------------------------------


def test_state_watching():
    """Single project with 0 changes -> ("watching", "... watching")."""
    _require()

    status_data = {"proj1": {"changed_count": 0}}
    state, tooltip = _compute_state(status_data)

    assert state == "watching", f"Expected state 'watching', got {state!r}"
    assert "watching" in tooltip.lower(), (
        f"Expected 'watching' in tooltip, got {tooltip!r}"
    )
    assert "Alteryx Git Companion" in tooltip, (
        f"Expected app name in tooltip, got {tooltip!r}"
    )


# ---------------------------------------------------------------------------
# test_state_idle
# ---------------------------------------------------------------------------


def test_state_idle():
    """Empty status dict -> ("idle", "Alteryx Git Companion")."""
    _require()

    status_data = {}
    state, tooltip = _compute_state(status_data)

    assert state == "idle", f"Expected state 'idle', got {state!r}"
    assert tooltip == "Alteryx Git Companion", (
        f"Expected 'Alteryx Git Companion', got {tooltip!r}"
    )


# ---------------------------------------------------------------------------
# test_state_multiple_projects_aggregates
# ---------------------------------------------------------------------------


def test_state_multiple_projects_aggregates():
    """Multiple projects: 1+2=3 total changes -> 'changes' state with '3 changes'."""
    _require()

    status_data = {"p1": {"changed_count": 1}, "p2": {"changed_count": 2}}
    state, tooltip = _compute_state(status_data)

    assert state == "changes", f"Expected state 'changes', got {state!r}"
    assert "3 changes" in tooltip, (
        f"Expected '3 changes' in aggregated tooltip, got {tooltip!r}"
    )


# ---------------------------------------------------------------------------
# test_state_singular_change
# ---------------------------------------------------------------------------


def test_state_singular_change():
    """Single change uses singular: '1 change detected' not '1 changes detected'."""
    _require()

    status_data = {"p1": {"changed_count": 1}}
    state, tooltip = _compute_state(status_data)

    assert state == "changes", f"Expected state 'changes', got {state!r}"
    assert "1 change detected" in tooltip, (
        f"Expected '1 change detected' (singular), got {tooltip!r}"
    )
    # Ensure it's not the plural form
    assert "1 changes" not in tooltip, (
        f"Should use singular '1 change', not '1 changes', got {tooltip!r}"
    )
