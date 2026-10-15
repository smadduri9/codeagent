"""The test-wide network guard blocks outbound connections."""

import socket

import pytest


def test_outbound_connection_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="network access is blocked"):
        socket.create_connection(("192.0.2.1", 443), timeout=0.1)
