"""Go/no-go probe: run the labelled failure cases through a running decider server.

Usage: python spike/probe.py [--url http://127.0.0.1:8099] [--out results/probe.json]
Prints per-case answers, accuracy, accuracy by confidence band and client-side latency.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from failure_cases import CASES, QUESTION, state_of  # noqa: E402


def ask(url: str, state: dict) -> tuple[dict, float]:
    body = json.dumps({"state": state, "questions": {"cause": QUESTION}}).encode()
    req = urllib.request.Request(f"{url}/v1/systemone", data=body, headers={"content-type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = json.loads(r.read())
    return payload["answers"]["cause"], (time.perf_counter() - t0) * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8099")
    ap.add_argument("--out", default="results/probe.json")
    args = ap.parse_args()

    ask(args.url, state_of(CASES[0]))  # warm-up, untimed
    rows, lat = [], []
    for case in CASES:
        ans, ms = ask(args.url, state_of(case))
        lat.append(ms)
        top = ans["choice"]
        rows.append({"label": case["label"], "pred": top, "confidence": ans.get("confidence"),
                     "probs": ans.get("probabilities"), "ms": round(ms, 1)})
        mark = "OK " if top == case["label"] else "XX "
        print(f"{mark}{case['label']:16} -> {top:16} conf {ans.get('confidence', 0):.3f}  {ms:7.1f} ms")

    n = len(rows)
    correct = sum(r["pred"] == r["label"] for r in rows)
    print(f"\naccuracy {correct}/{n} = {correct / n:.2f}")
    for lo, hi in ((0.9, 1.01), (0.5, 0.9), (0.0, 0.5)):
        band = [r for r in rows if lo <= (r["confidence"] or 0) < hi]
        if band:
            ok = sum(r["pred"] == r["label"] for r in band)
            print(f"confidence [{lo:.1f},{min(hi, 1):.1f}): {len(band):2} answers, accuracy {ok}/{len(band)}")
    per = Counter(r["label"] for r in rows if r["pred"] == r["label"])
    print("per class correct:", dict(per))
    s = sorted(lat)
    print(f"latency ms: median {statistics.median(s):.1f}  p90 {s[int(0.9 * (n - 1))]:.1f}  max {s[-1]:.1f}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"rows": rows, "accuracy": correct / n}, indent=2))


if __name__ == "__main__":
    main()
