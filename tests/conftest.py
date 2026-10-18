"""Shared fixtures: serve the demo app on loopback only, plus the Heal or Halt collector hook.

Environment knobs (all optional; the plain `make test` run sets none of them):
    HOH_APP_DIR       serve this directory instead of demo-app/ (the mutation monkey uses it)
    HOH_APP_MODE      normal | down | slow | error500   -- environment failures, for real
    HOH_FAILURES_DIR  when set, every failing test writes one collector record there
    HOH_TIMEOUT_MS    Playwright action/expect timeout (default 3000)
    HOH_ROOT          project root, when these tests run from a copied workspace
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("HOH_ROOT", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / "patterns" / "policy-can-heal"))
sys.path.insert(0, str(ROOT))

TIMEOUT_MS = int(os.environ.get("HOH_TIMEOUT_MS", "3000"))
MODE = os.environ.get("HOH_APP_MODE", "normal")


class _Server(http.server.ThreadingHTTPServer):
    """The stdlib default listen backlog is 5. A multi-file app (TodoMVC loads 8 scripts at once) then
    gets ERR_CONNECTION_RESET on a script and fails to start, which looks like a real bug. Raise it."""

    request_queue_size = 64


class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass

    def do_GET(self):  # noqa: N802 (stdlib name)
        if MODE == "error500":
            self.send_response(500)
            self.send_header("content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>500 Internal Server Error</h1><p>upstream unavailable</p>")
            return
        if MODE == "slow":
            time.sleep(TIMEOUT_MS / 1000 * 2)
        super().do_GET()


@pytest.fixture(scope="session")
def app_url():
    if MODE == "down":  # a real refused connection: grab a free loopback port, then close it
        import socket

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            dead = s.getsockname()[1]
        yield f"http://127.0.0.1:{dead}/index.html"
        return
    app_dir = os.environ.get("HOH_APP_DIR", str(ROOT / "demo-app"))
    handler = functools.partial(_Handler, directory=app_dir)
    server = _Server(("127.0.0.1", 0), handler)  # explicit loopback bind
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()


@pytest.fixture(autouse=True)
def _short_timeouts(request):
    """Fail fast: a broken locator should cost seconds, not Playwright's default 30 s."""
    if "page" in request.fixturenames:
        from playwright.sync_api import expect

        page = request.getfixturevalue("page")
        page.set_default_timeout(TIMEOUT_MS)
        page.set_default_navigation_timeout(TIMEOUT_MS)
        expect.set_options(timeout=TIMEOUT_MS)
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    out_dir = os.environ.get("HOH_FAILURES_DIR")
    if not out_dir or report.when != "call" or not report.failed:
        return
    from hoh.collect import build_state, write_record

    error = str(call.excinfo.value) if call.excinfo else report.longreprtext
    if call.excinfo and call.excinfo.typename not in error:
        error = f"{call.excinfo.typename}: {error}"
    page = item.funcargs.get("page")
    url = item.funcargs.get("app_url", "")
    state = build_state(test=item.name.split("[")[0], error=error, page=page, url=url)
    write_record(out_dir, {"test_id": item.nodeid, "state": state, "raw_error": error[:2000]})
