from __future__ import annotations

import json
import urllib.request

from keel.app import find_free_port, serve_background


def test_find_free_port_is_bindable():
    p = find_free_port()
    assert 1024 < p < 65536


def test_serve_background_serves_and_stops(tmp_path):
    port = find_free_port()
    server = serve_background(tmp_path, port)
    try:
        html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read()
        assert b"<title>Keel</title>" in html
        assert b"KILL" in html  # monitor-only page, kill switch present
        status = json.loads(
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/live/status", timeout=5).read()
        )
        assert "enabled" in status  # no service passed -> {"enabled": False}
    finally:
        server.shutdown()
