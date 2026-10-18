"""Collector: turn a real Playwright failure into Decider's compact state (< 500 tokens).

The state has five fields, the same ones question.json was written against:
    step       the test and the line that failed
    locator    the locator Playwright was waiting for (if any)
    error      the first lines of the Playwright error
    a11y_diff  '-' old / '+' new lines between the clean app's aria snapshot and now
    commit     the commit message that triggered the run

Everything here is deterministic: no model is involved in collecting evidence.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "eval" / "baseline_aria.yaml"
LOCATOR_RE = re.compile(r"waiting for ((?:get_by_\w+|locator)\(.*)$", re.MULTILINE)
MAX_DIFF_LINES = 14


def first_lines(text: str, n: int = 4, width: int = 220) -> str:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    # Drop pytest's "E   " prefixes and keep the informative head.
    lines = [re.sub(r"^E\s+", "", ln) for ln in lines]
    return "\n".join(ln[:width] for ln in lines[:n])


def extract_locator(error: str) -> str:
    m = LOCATOR_RE.search(error)
    return m.group(1) if m else ""


def aria_diff(old: str, new: str) -> str:
    out = [ln for ln in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
           if (ln.startswith("+") or ln.startswith("-")) and not ln.startswith(("+++", "---"))]
    if not out:
        return "(no change)"
    if len(out) > MAX_DIFF_LINES:
        out = out[:MAX_DIFF_LINES] + [f"... {len(out) - MAX_DIFF_LINES} more changed lines"]
    return "\n".join(out)


def snapshot_now(page, url: str) -> str:
    """Aria snapshot of the page as freshly loaded, so the diff shows structural UI change only."""
    try:
        page.goto(url, timeout=3000)
        return page.locator("body").aria_snapshot(timeout=3000)
    except Exception as exc:  # the page itself did not load: that IS the evidence
        return f"- page failed to load: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}"


def build_state(*, test: str, error: str, page, url: str, commit: str | None = None) -> dict:
    base = Path(os.environ.get("HOH_BASELINE", BASELINE))  # `hoh run` points this at the repo's last green commit
    baseline = base.read_text() if base.exists() else ""
    now = snapshot_now(page, url) if page is not None else ""
    head = first_lines(error)
    return {
        "step": test,
        "locator": extract_locator(error) or "(none)",
        "error": head,
        "a11y_diff": aria_diff(baseline, now),
        "commit": commit or os.environ.get("HOH_COMMIT", "(unknown)"),
    }


def write_record(out_dir: str, record: dict) -> Path:
    path = Path(out_dir) / f"{int(time.time() * 1000)}-{record['test_id'].replace('/', '_').replace('::', '__')}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    return path
