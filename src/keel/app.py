"""Desktop-app entry point — double-click, a Keel window opens.

`run_app` starts the local server on a background thread and then opens the
dashboard in a **native window** via pywebview if it is installed (feels like a
real app, no browser chrome). If pywebview isn't available it falls back to
opening your default browser — so it always works, and installing the extra
just makes it nicer:

    pip install -e ".[desktop]"

Entry points: the console command ``keel app`` and the windowed launcher
``keel-app`` (no console window on Windows) both call ``main`` here.
"""

from __future__ import annotations

import socket
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from keel.ui import make_handler


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve_background(data_dir: Path, port: int, service=None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(data_dir, service))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_app(data_dir: str | Path = "data", port: int | None = None) -> None:
    from keel.env import load_env
    from keel.service import LiveService

    load_env()
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Opening Keel starts the paper bot (auto-arms per config; paper only).
    import contextlib

    service = LiveService(data_dir)
    with contextlib.suppress(Exception):  # UI still opens and explains any failure
        service.start()

    port = port or find_free_port()
    server = serve_background(data_dir, port, service)
    url = f"http://127.0.0.1:{port}"

    try:
        import webview  # pywebview — native window
    except ImportError:
        webview = None

    if webview is not None:
        webview.create_window("Keel", url, width=1320, height=880, min_size=(900, 600))
        webview.start()  # blocks until the window is closed
        server.shutdown()
        return

    # Fallback: browser + keep serving.
    import contextlib
    import webbrowser

    print(f"Keel running at {url}  (install '.[desktop]' for a native window)")
    print("Close this window / press Ctrl+C to quit.")
    with contextlib.suppress(Exception):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(prog="keel-app", description="Keel desktop dashboard")
    p.add_argument("--dir", default="data")
    p.add_argument("--port", type=int, default=None)
    args = p.parse_args()
    run_app(args.dir, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
