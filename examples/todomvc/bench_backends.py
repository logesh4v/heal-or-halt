"""Fair latency bench: local Decider vs hosted decider-cloud, same states, same question, interleaved.

20 timed calls per backend (4 real TodoMVC failure states x 5 reps), plus 2 untimed warm-ups each.
Calls alternate local, cloud, local, cloud... so both see the same machine load at the same moment.
Run from the heal-or-halt root with `make serve` up and DECIDER_URL + DECIDER_API_KEY in the environment:
    .venv/bin/python examples/todomvc/bench_backends.py
"""

import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "patterns/policy-can-heal")
import handler  # noqa: E402

KEY, URL = os.environ.get("DECIDER_API_KEY", ""), os.environ.get("DECIDER_URL", "")
if not (KEY and URL):
    sys.exit("set DECIDER_URL and DECIDER_API_KEY (the cloud side needs both)")
REPS = 5
cases = Path("examples-run/todomvc/cases")
states = []
for name in ["rename-placeholder", "counter-bug", "combo", "rename-clear"]:
    rec = sorted((cases / name / ".hoh" / "initial").glob("*.json"))[0]
    states.append((name, json.loads(rec.read_text())["state"]))


def call(which: str, state: dict) -> tuple[float, float | None, float]:
    """(client ms, server-reported ms or None, can_heal)."""
    if which == "local":
        os.environ.pop("DECIDER_API_KEY", None)
        os.environ.pop("DECIDER_URL", None)
    else:
        os.environ["DECIDER_API_KEY"], os.environ["DECIDER_URL"] = KEY, URL
    name, base, auth = handler.backend()
    path = "/v1/systemone" if name == "local" else "/v1/decide"
    st = handler._mask_local_urls(state) if name == "cloud" else state
    req = handler.urllib.request.Request(f"{base}{path}", headers={"content-type": "application/json", **auth},
                                         data=json.dumps({"state": st, "questions": handler.QUESTIONS}).encode())
    t = time.perf_counter()
    with handler.urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
        body = json.loads(r.read())
    ms = (time.perf_counter() - t) * 1000
    return ms, body.get("latency_ms"), float(body["answers"]["can_heal"]["noul"])


for which in ("local", "cloud"):
    for _ in range(2):
        call(which, states[0][1])  # warm-up, not counted

rows = {"local": [], "cloud": []}
server, p = [], {"local": {}, "cloud": {}}
for name, s in states:
    for _ in range(REPS):
        for which in ("local", "cloud"):
            ms, srv, ch = call(which, s)
            rows[which].append(ms)
            p[which].setdefault(name, ch)
            if srv is not None:
                server.append(srv)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


res = {"calls_per_backend": len(rows["local"]), "states": [n for n, _ in states],
       "client_ms": {k: {"p50": round(statistics.median(v)), "p95": round(pct(v, 0.95)),
                         "min": round(min(v)), "max": round(max(v))} for k, v in rows.items()},
       "cloud_server_ms": {"p50": round(statistics.median(server)), "p95": round(pct(server, 0.95))},
       "can_heal": p}
print(json.dumps(res, indent=1))
Path("results/bench_backends.json").write_text(json.dumps(res, indent=1))
