"""Unit tests for find_available_port() from app.main."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from app.main import find_available_port


def test_find_available_port_returns_7433():
    """find_available_port() returns 7433 when it is free."""
    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    with patch("socket.socket", return_value=mock_sock):
        port, sock = find_available_port(start=7433, count=11)
    assert port == 7433
    assert sock is mock_sock


def test_find_available_port_skips_occupied():
    """When start port is bound by another socket, returns next free port."""
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Do NOT set SO_REUSEADDR on the blocker: on Linux, if both sockets set
    # SO_REUSEADDR the kernel allows them to share the port, defeating the test.
    blocker.bind(("127.0.0.1", 19900))
    try:
        port, sock = find_available_port(start=19900, count=11)
        try:
            assert port == 19901
        finally:
            sock.close()
    finally:
        blocker.close()


def test_find_available_port_raises_when_all_full():
    """When all ports in range are bound, raises OSError."""
    blockers: list[socket.socket] = []
    try:
        for p in range(19900, 19911):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # No SO_REUSEADDR — see test_find_available_port_skips_occupied.
            s.bind(("127.0.0.1", p))
            blockers.append(s)
        with pytest.raises(OSError):
            find_available_port(start=19900, count=11)
    finally:
        for s in blockers:
            s.close()
