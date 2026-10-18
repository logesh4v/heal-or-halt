"""Reusable decision pattern: policy-can-heal.

One sharp yes/no (can_heal) gates a risky write action; one choice (halt_reason) routes
the refusal. The model classifies; this code decides, in three confidence bands:

    can_heal >= HEAL  -> heal  (proceed with the fix)
    ASK <= p < HEAL   -> ask   (a human approves first)
    p < ASK           -> halt  (no code change; file an issue for halt_reason's owner)

Two hard rules apply whatever the model says: a fix is never trusted unless the re-run
passed, and a new locator that still contains the old name proves nothing (Playwright's
role-name match is a case-insensitive substring match).

Backend, chosen by the environment (read on every call, never stored in code):
    DECIDER_API_KEY unset -> local strands-decider server, POST {DECIDER_URL or 127.0.0.1:8099}/v1/systemone
    DECIDER_API_KEY set   -> hosted decider-cloud, POST {DECIDER_URL}/v1/decide with a Bearer key (https only)
The thresholds below were calibrated on the LOCAL model; re-run the eval before trusting them on cloud.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

QUESTIONS: dict[str, Any] = json.loads((Path(__file__).with_name("question.json")).read_text())
HEAL = 0.73  # conformal risk control, alpha=0.05 on the calibration split (thresholds.md)
ASK = 0.55
DEFAULT_URL = "http://127.0.0.1:8099"  # the Decider server has no auth: loopback only
_LOOPBACK = re.compile(r"https?://(?:127\.0\.0\.1|localhost|0\.0\.0\.0|\[::1\])(?::\d+)?", re.I)


@dataclass(frozen=True)
class Verdict:
    action: str          # "heal" | "ask" | "halt"
    can_heal: float
    halt_reason: str
    reason: str

    def line(self) -> str:
        """The console line shown on screen (the hackathon video must show confidence)."""
        return f"can_heal {self.can_heal:.2f} -> {self.action.upper()} ({self.reason})"


def backend() -> tuple[str, str, dict[str, str]]:
    """(name, base_url, auth_headers) for the Decider this process should call."""
    key = os.environ.get("DECIDER_API_KEY", "").strip()
    url = os.environ.get("DECIDER_URL", "").strip().rstrip("/")
    if not key:
        return "local", url or DEFAULT_URL, {}
    if not url.startswith("https://"):
        # Never send the key to the loopback default or over plain http.
        raise RuntimeError("DECIDER_API_KEY is set, so DECIDER_URL must be the https:// decider-cloud URL")
    return "cloud", url, {"authorization": f"Bearer {key}"}


def _mask_local_urls(state: dict[str, str]) -> dict[str, str]:
    """Cloud only: replace loopback URLs with <app-url>.

    Found on the hosted decider-cloud: its AWS WAF blocks (HTTP 403) any body carrying a
    http://127.0.0.1:PORT address (an SSRF rule). The test server's port is noise to the
    model anyway; the error text around it ("ERR_CONNECTION_REFUSED") is what it reads.
    """
    return {k: _LOOPBACK.sub("<app-url>", v) if isinstance(v, str) else v for k, v in state.items()}


def ask_decider(state: dict[str, str], url: str | None = None, timeout: float = 60.0,
                retries: int = 5) -> dict[str, Any]:
    name, base, auth = backend()
    base = (url or base).rstrip("/")
    path = "/v1/systemone" if name == "local" else "/v1/decide"
    if name == "cloud":
        state = _mask_local_urls(state)
    body = json.dumps({"state": state, "questions": QUESTIONS}).encode()
    headers = {"content-type": "application/json", **auth}
    for attempt in range(retries):
        req = urllib.request.Request(f"{base}{path}", data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (loopback or https cloud)
                return json.loads(resp.read())["answers"]
        except urllib.error.HTTPError as e:
            # Cloud only: 429 rate/concurrency limit, 503 overloaded -> wait as told, then retry.
            if name == "cloud" and e.code in (429, 503) and attempt < retries - 1:
                time.sleep(min(float(e.headers.get("Retry-After") or 6), 60.0))
                continue
            raise
    raise RuntimeError("unreachable")


def failure_kind(error: str) -> str:
    """Deterministic pre-classification of a Playwright error (no model).

    Only a *locator* failure is ever a heal candidate. Assertions are never healed: a
    test that found its element but saw the wrong value is reporting the product, and
    rewriting it would hide the bug.
    """
    e = error.lower()
    if "net::err" in e or "connection refused" in e or "err_connection" in e or "page.goto" in e:
        return "navigation"
    if "locator expected" in e or "assertionerror" in e or "expected" in e and "received" in e:
        return "assertion"
    if "timeout" in e and ("waiting for get_by_" in e or "waiting for locator" in e):
        return "locator"
    if "strict mode violation" in e:
        return "locator"
    return "other"


def decide(answers: dict[str, Any], *, old_name: str = "", new_name: str = "",
           rerun_green: bool | None = None, heal: float = HEAL, ask: float = ASK,
           kind: str = "locator", a11y_diff: str = "") -> Verdict:
    """Pure policy over Decider's typed answers. No I/O, so it is unit-testable."""
    p = float(answers["can_heal"]["noul"])
    owner = str(answers.get("halt_reason", {}).get("choice", "developer"))
    if kind == "locator" and a11y_diff.strip() == "(no change)":
        owner = "test_author"  # the page did not change at all, so the test's own locator is wrong
    if kind == "assertion":
        return Verdict("halt", p, "developer", "assertion failed: assertions are never healed")
    if kind == "navigation":
        return Verdict("halt", p, "platform", "page did not load: environment problem")
    if p < ask:
        return Verdict("halt", p, owner, f"below {ask:.2f}: route to {owner}")
    if new_name and old_name and old_name.lower() in new_name.lower():
        return Verdict("halt", p, "test_author", "new locator still contains the old name")
    if new_name and a11y_diff and not any(f'"{new_name}"' in ln for ln in a11y_diff.splitlines()
                                          if ln.startswith("+")):
        # Found on real TodoMVC: a guessed name can pass the re-run because Playwright matches by substring.
        return Verdict("halt", p, "test_author", "new name is not on a '+' line of the evidence")
    if rerun_green is False:
        return Verdict("halt", p, owner, "healed test still red on re-run")
    if p < heal:
        return Verdict("ask", p, owner, f"between {ask:.2f} and {heal:.2f}: human approves")
    return Verdict("heal", p, owner, f">= {heal:.2f}")


def make_gate(url: str | None = None, guarded_tool: str = "open_pr"):
    """Build a Strands InterventionHandler that guards `guarded_tool`.

    The agent must put the failure in agent.state["failure"] before calling the tool:
    {"state": {...compact state...}, "old_name": str, "new_name": str, "rerun_green": bool}
    """
    from strands.interventions import Confirm, Deny, InterventionHandler, Proceed

    class HealGate(InterventionHandler):
        name = "policy-can-heal-gate"

        def __init__(self) -> None:
            self.log: list[Verdict] = []

        def before_tool_call(self, event, **kwargs):
            if event.tool_use["name"] != guarded_tool:
                return Proceed()
            failure = event.agent.state.get("failure") or {}
            if not failure.get("state"):
                return Deny(reason="No failure state recorded; refusing to open a PR blind.")
            st = failure["state"]
            v = decide(ask_decider(st, url),
                       old_name=failure.get("old_name", ""), new_name=failure.get("new_name", ""),
                       rerun_green=failure.get("rerun_green"),
                       kind=failure_kind(st.get("error", "")), a11y_diff=st.get("a11y_diff", ""))
            self.log.append(v)
            print(v.line())
            if v.action == "heal":
                return Proceed(reason=v.line())
            if v.action == "ask":
                return Confirm(prompt=f"{v.line()}. Open this PR anyway?")
            return Deny(reason=f"{v.line()}. Do not change code; file an issue for {v.halt_reason}.")

    return HealGate()
