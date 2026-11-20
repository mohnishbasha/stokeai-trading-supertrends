# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Unit tests run with outbound network blocked (TS-SEC-037, Sprint 1 checklist)."""

import socket

import pytest
from pytest_socket import SocketConnectBlockedError


def test_unit_network_outbound_connection_attempt_fails_blocked() -> None:
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(("93.184.216.34", 80), timeout=1)


def test_unit_network_outbound_hostname_connection_attempt_fails_blocked() -> None:
    # pytest-socket blocks the connect; inside CI's network namespace (GD-003) name resolution
    # fails first with socket.gaierror. Either way the hostname is unreachable.
    with pytest.raises((SocketConnectBlockedError, socket.gaierror)):
        socket.create_connection(("example.com", 443), timeout=1)


def test_unit_network_loopback_is_allowed_by_policy() -> None:
    srv = socket.socket()
    try:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        client = socket.create_connection(srv.getsockname(), timeout=1)
        client.close()
    finally:
        srv.close()
