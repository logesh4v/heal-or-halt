"""Write eval/baseline_aria.yaml: the clean app's aria snapshot, freshly loaded.

The collector diffs every failure against this, so the diff shows structural UI change only.
Run: .venv/bin/python -m hoh.baseline
"""

from __future__ import annotations

import functools
import http.server
import threading

from playwright.sync_api import sync_playwright

from hoh.collect import BASELINE, ROOT


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class _Server(http.server.ThreadingHTTPServer):
    request_queue_size = 64  # the default 5 resets connections when a multi-file app loads many scripts


def main() -> None:
    snap = capture(ROOT / "demo-app")
    BASELINE.parent.mkdir(exist_ok=True)
    BASELINE.write_text(snap + "\n")
    print(f"wrote {BASELINE}:\n{snap}")


def capture(app_dir) -> str:
    """Aria snapshot of index.html in app_dir, served on loopback and freshly loaded in Chrome."""
    handler = functools.partial(_Quiet, directory=str(app_dir))
    server = _Server(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/index.html")
            snap = page.locator("body").aria_snapshot()
            browser.close()
    finally:
        server.shutdown()
    return snap


if __name__ == "__main__":
    main()
