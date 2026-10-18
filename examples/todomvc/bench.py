"""Latency + token bench on the REAL TodoMVC failure states: Decider 2B (local) vs Nova Micro vs Nova Pro.

Each model answers the same can_heal question on the same collector state, 5 reps, warm.
Run from the heal-or-halt root after `make todomvc`: .venv/bin/python examples/todomvc/bench.py
"""

import json
import statistics
import sys
import time
from pathlib import Path

import boto3

sys.path.insert(0, "patterns/policy-can-heal")
sys.path.insert(0, ".")
from handler import ask_decider  # noqa: E402

from hoh.agent import veto_opinion  # noqa: E402,F401  (Nova Pro uses the shipped veto prompt below)
from hoh.eval import NOVA_MICRO, nova_baseline  # noqa: E402

NOVA_PRO = "us.amazon.nova-pro-v1:0"
REPS = 5
cases = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("examples-run/todomvc/cases")
states = []
for c in sorted(cases.iterdir()):
    recs = sorted((c / ".hoh" / "initial").glob("*.json"))
    if recs:
        states.append((c.name, json.loads(recs[0].read_text())["state"]))

client = boto3.Session(profile_name="default").client("bedrock-runtime", region_name="us-east-1")
ask_decider(states[0][1])  # warm-up, not counted
rows = {"decider": [], "nova_micro": [], "nova_pro": []}
tok = {"nova_micro": [0, 0], "nova_pro": [0, 0]}
for name, s in states:
    for _ in range(REPS):
        t = time.perf_counter(); ask_decider(s); rows["decider"].append((time.perf_counter() - t) * 1000)
        _, ms, i, o = nova_baseline(client, s); rows["nova_micro"].append(ms); tok["nova_micro"][0] += i; tok["nova_micro"][1] += o
        prompt = ("A browser test failed. Is it SAFE to auto-repair the test's locator (same control, new name or "
                  "position, nothing broken)? Answer SAFE or UNSAFE.\n\n" + json.dumps(s, ensure_ascii=False))
        t = time.perf_counter()
        out = client.converse(modelId=NOVA_PRO, messages=[{"role": "user", "content": [{"text": prompt}]}],
                              inferenceConfig={"maxTokens": 5, "temperature": 0})
        rows["nova_pro"].append((time.perf_counter() - t) * 1000)
        tok["nova_pro"][0] += out["usage"]["inputTokens"]; tok["nova_pro"][1] += out["usage"]["outputTokens"]


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


n = len(states) * REPS
res = {"states": [s for s, _ in states], "calls_per_model": n,
       "latency_ms": {k: {"p50": round(statistics.median(v)), "p95": round(pct(v, 0.95))} for k, v in rows.items()},
       "tokens_per_call": {k: {"input": round(v[0] / n), "output": round(v[1] / n)} for k, v in tok.items()}}
print(json.dumps(res, indent=1))
Path("results/bench_todomvc.json").write_text(json.dumps(res, indent=1))
