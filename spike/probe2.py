"""Probe 2: (a) option-order bias -- same choice question with options reversed;
(b) the binary Heal-or-Halt framing as one noul question, plus a 3-way halt reason.

Usage: python spike/probe2.py [--url http://127.0.0.1:8099]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from failure_cases import CASES, QUESTION, state_of  # noqa: E402

HEALABLE = {"label_drift", "layout_move"}

REVERSED = {**QUESTION, "criteria": dict(reversed(list(QUESTION["criteria"].items())))}

CAN_HEAL = {
    "type": "noul",
    "instructions": "Does the element the test was looking for still exist on the page, only renamed or moved, with the app otherwise working?",
    "criteria": {
        "true": "the accessibility diff shows the same control under a new name or in a new place, and nothing indicates the app or environment is broken",
        "false": "the app shows a wrong value or error, the page did not load, the environment failed, or the test itself is wrong",
    },
}

HALT_REASON = {
    "type": "choice",
    "instructions": "A browser end-to-end test failed. Who needs to act on it?",
    "criteria": {
        "developer": "the app now behaves wrongly: a wrong value, a server error, missing data or a broken flow",
        "platform": "the environment failed: server unreachable, network or DNS error, disk full, browser crash, or it passed on retry",
        "test_author": "the test is wrong: a typo in the locator, a wrong fixture or expectation, an ambiguous locator or invalid input",
    },
}
HALT_OF = {"real_regression": "developer", "env_flake": "platform", "test_bug": "test_author"}


def ask(url: str, state: dict, questions: dict) -> tuple[dict, float]:
    body = json.dumps({"state": state, "questions": questions}).encode()
    req = urllib.request.Request(f"{url}/v1/systemone", data=body, headers={"content-type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["answers"], (time.perf_counter() - t0) * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8099")
    args = ap.parse_args()
    fwd = json.loads(Path("results/probe_v1.json").read_text())["rows"]

    ask(args.url, state_of(CASES[0]), {"q": CAN_HEAL})  # warm-up
    rev_ok = flips = 0
    heal_rows, halt_ok, halt_n, lat3 = [], 0, 0, []
    for case, f in zip(CASES, fwd):
        a, _ = ask(args.url, state_of(case), {"cause": REVERSED})
        rev = a["cause"]["choice"]
        rev_ok += rev == case["label"]
        flips += rev != f["pred"]
        # one request, three questions: shows the shared-prefix cost of extra questions
        a, ms = ask(args.url, state_of(case), {"can_heal": CAN_HEAL, "halt_reason": HALT_REASON, "cause": QUESTION})
        lat3.append(ms)
        p = a["can_heal"]["noul"]
        heal_rows.append((case["label"], p))
        if case["label"] in HALT_OF:
            halt_n += 1
            halt_ok += a["halt_reason"]["choice"] == HALT_OF[case["label"]]
        print(f"{case['label']:16} fwd {f['pred']:16} rev {rev:16} P(can_heal) {p:.3f} halt->{a['halt_reason']['choice']:11} "
              f"({a['halt_reason']['confidence']:.2f})  3q {ms:6.1f} ms")

    n = len(CASES)
    print(f"\nreversed order accuracy {rev_ok}/{n}; answer changed on {flips}/{n} cases vs forward order")
    for tau in (0.5, 0.7, 0.8, 0.9):
        tp = sum(1 for lab, p in heal_rows if p >= tau and lab in HEALABLE)
        fp = sum(1 for lab, p in heal_rows if p >= tau and lab not in HEALABLE)
        print(f"can_heal >= {tau}: heals {tp}/10 healable, wrongly heals {fp}/15 non-healable")
    ok = sum((p >= 0.5) == (lab in HEALABLE) for lab, p in heal_rows)
    print(f"can_heal binary accuracy at 0.5: {ok}/{n}")
    print(f"halt_reason accuracy on the 15 non-healable cases: {halt_ok}/{halt_n}")
    print(f"3 questions in one request: median {statistics.median(lat3):.1f} ms, max {max(lat3):.1f} ms")


if __name__ == "__main__":
    main()
