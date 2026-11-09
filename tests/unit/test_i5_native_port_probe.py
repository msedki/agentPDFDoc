"""Real ephemeral loopback sockets only; no model, OCR or native service."""

from __future__ import annotations

import errno
import socket
import sys
import time

import psutil
import pytest

from tools.qualification import run_grounded_native as launcher


def server_time_wait(reuse: bool) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if reuse:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            accepted, _ = listener.accept()
            accepted.close()
            assert client.recv(1) == b""
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        states = {item.status for item in psutil.net_connections(kind="tcp") if item.laddr and item.laddr.port == port}
        if states == {psutil.CONN_TIME_WAIT}:
            return port
        time.sleep(0.01)
    pytest.fail("The controlled server-side TIME_WAIT was not observed.")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux socket-state counterexample; no Windows behavior inferred.")
def test_native_preflight_allows_a_real_reusable_closed_server_port():
    port = server_time_wait(True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as historical_probe:
        with pytest.raises(OSError) as previous:
            historical_probe.bind(("127.0.0.1", port))
        assert previous.value.errno == errno.EADDRINUSE
    launcher.available_port(port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as restarted:
        restarted.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        restarted.bind(("127.0.0.1", port))
        restarted.listen()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux requires reuse on the closed listener as well.")
def test_native_preflight_keeps_nonreusable_time_wait_refused():
    port = server_time_wait(False)
    with pytest.raises(OSError, match=f"Port loopback {port} indisponible") as failure:
        launcher.available_port(port)
    assert failure.value.errno == errno.EADDRINUSE
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as restarted:
        restarted.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with pytest.raises(OSError):
            restarted.bind(("127.0.0.1", port))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Native qualification launcher targets Linux.")
@pytest.mark.parametrize("address", ["127.0.0.1", "0.0.0.0"])
@pytest.mark.parametrize("reuse", [False, True])
def test_native_preflight_refuses_an_active_foreign_listener_without_stopping_it(address, reuse):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if reuse:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((address, 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(OSError, match=f"Port loopback {port} indisponible") as failure:
            launcher.available_port(port)
        assert failure.value.errno == errno.EADDRINUSE
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            accepted, _ = listener.accept()
            with accepted:
                accepted.sendall(b"still-owned-by-the-test")
                assert client.recv(64) == b"still-owned-by-the-test"
