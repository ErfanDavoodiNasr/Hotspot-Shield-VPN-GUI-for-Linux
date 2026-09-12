"""IP service unit tests with local HTTP server."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from hotspotshield_gui.services.ip_service import IpService
from hotspotshield_gui.utils.errors import NetworkProbeError


class _Handler(BaseHTTPRequestHandler):
    body = b'{"ip":"203.0.113.10","city":"Testville","country":"TS"}'

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


@pytest.fixture()
def ip_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield f"http://{host}:{port}/json"
    server.shutdown()


def test_ip_lookup_json(ip_server: str) -> None:
    svc = IpService(endpoints=[ip_server], timeout=2)
    info = svc.lookup()
    assert info.ip == "203.0.113.10"
    assert info.city == "Testville"


def test_ip_lookup_all_fail() -> None:
    svc = IpService(endpoints=["http://127.0.0.1:9/nope"], timeout=0.3)
    with pytest.raises(NetworkProbeError):
        svc.lookup()
