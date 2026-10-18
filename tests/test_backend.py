"""Decider backend selection: local by default, hosted cloud only when DECIDER_API_KEY is set.

No network: urlopen is replaced by a fake that records each request.
"""

import io
import json
import urllib.error

import handler
import pytest

ANSWERS = {"can_heal": {"type": "noul", "noul": 0.9}, "halt_reason": {"choice": "developer"}}


class FakeHTTP:
    def __init__(self, errors=()):
        self.calls, self.errors = [], list(errors)

    def __call__(self, req, timeout=None):
        self.calls.append(req)
        if self.errors:
            code = self.errors.pop(0)
            raise urllib.error.HTTPError(req.full_url, code, "busy", {"Retry-After": "0"}, io.BytesIO(b"{}"))
        return io.BytesIO(json.dumps({"answers": ANSWERS}).encode())


@pytest.fixture
def http(monkeypatch):
    fake = FakeHTTP()
    monkeypatch.setattr(handler.urllib.request, "urlopen", fake)
    monkeypatch.setattr(handler.time, "sleep", lambda s: None)
    monkeypatch.delenv("DECIDER_API_KEY", raising=False)
    monkeypatch.delenv("DECIDER_URL", raising=False)
    return fake


def test_no_key_uses_local_server_unchanged(http):
    assert handler.ask_decider({"error": "x"}) == ANSWERS
    req = http.calls[0]
    assert req.full_url == "http://127.0.0.1:8099/v1/systemone"
    assert req.get_header("Authorization") is None
    assert json.loads(req.data) == {"state": {"error": "x"}, "questions": handler.QUESTIONS}


def test_key_uses_cloud_with_bearer(http, monkeypatch):
    monkeypatch.setenv("DECIDER_API_KEY", "dcd_live_test")
    monkeypatch.setenv("DECIDER_URL", "https://example.cloudfront.net/")
    handler.ask_decider({"error": "x"})
    req = http.calls[0]
    assert req.full_url == "https://example.cloudfront.net/v1/decide"
    assert req.get_header("Authorization") == "Bearer dcd_live_test"


def test_key_is_never_sent_to_loopback_or_http(http, monkeypatch):
    monkeypatch.setenv("DECIDER_API_KEY", "dcd_live_test")
    with pytest.raises(RuntimeError, match="https"):
        handler.ask_decider({})
    monkeypatch.setenv("DECIDER_URL", "http://example.com")
    with pytest.raises(RuntimeError, match="https"):
        handler.ask_decider({})
    assert http.calls == []


def test_cloud_retries_when_busy_then_succeeds(http, monkeypatch):
    monkeypatch.setenv("DECIDER_API_KEY", "dcd_live_test")
    monkeypatch.setenv("DECIDER_URL", "https://example.cloudfront.net")
    http.errors = [429, 503]
    assert handler.ask_decider({}) == ANSWERS
    assert len(http.calls) == 3


def test_local_does_not_retry(http):
    http.errors = [503]
    with pytest.raises(urllib.error.HTTPError):
        handler.ask_decider({})
    assert len(http.calls) == 1


def test_cloud_masks_loopback_urls_but_local_sends_them_as_is(http, monkeypatch):
    err = {"error": "Page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:65265/index.html"}
    handler.ask_decider(err)
    assert json.loads(http.calls[0].data)["state"] == err  # local: untouched
    monkeypatch.setenv("DECIDER_API_KEY", "dcd_live_test")
    monkeypatch.setenv("DECIDER_URL", "https://example.cloudfront.net")
    handler.ask_decider(err)
    sent = json.loads(http.calls[1].data)["state"]["error"]
    assert sent == "Page.goto: net::ERR_CONNECTION_REFUSED at <app-url>/index.html"
