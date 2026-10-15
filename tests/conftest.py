"""Test-wide guard: no test may open a network connection unless marked live.

A provider test once found a developer's real API key in .env and called the API.
This makes any such mistake fail loudly instead of spending money.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from typing import Any

import pytest

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_local(address: Any) -> bool:
    if isinstance(address, tuple) and address:
        return str(address[0]) in _LOCAL_HOSTS
    return isinstance(address, (str, bytes))  # unix domain sockets


@pytest.fixture(autouse=True)
def _block_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    if request.node.get_closest_marker("live") is not None:
        yield
        return
    real_connect = socket.socket.connect

    def guarded(self: socket.socket, address: Any) -> Any:
        if not _is_local(address):
            raise RuntimeError(f"network access is blocked in tests: {address!r}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield
