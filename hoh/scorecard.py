"""Agent scorecard: run the full agent on every mutation and check the OUTCOME against ground truth.

Correct outcome:  heal -> PR on a heal/ branch with a green re-run
                  developer / platform / test_author / combo -> issue, no heal branch, tests untouched
Writes results/AGENT_SCORECARD.md and results/agent_scorecard.json.
    .venv/bin/python -m hoh.scorecard          (needs `make serve` + AWS profile; ~10 min)
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import time

from hoh.agent import run_agent
from hoh.collect import ROOT
from hoh.monkey import MUTATIONS


def main() -> None:
    import sys

    from handler import backend

    name, base, _ = backend()
    print(f"decider backend: {name} ({base})", flush=True)
    sfx = "" if name == "local" else f"_{name}"  # cloud results never overwrite the local record
    only = set(sys.argv[1:])
    old = {}
    prev = ROOT / "results" / f"agent_scorecard{sfx}.json"
    if only and prev.exists():
        old = {r["mutation"]: r for r in json.loads(prev.read_text())}
    rows = []
    for m in MUTATIONS:
        if only and m.id not in only:
            if m.id in old:
                rows.append(old[m.id])
            continue
        t = time.perf_counter()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run = run_agent(m.id)
        secs = time.perf_counter() - t
        branches = subprocess.run(["git", "branch", "--list", "heal/*"], cwd=run.ws, capture_output=True,
                                  text=True).stdout.split()
        dirty = subprocess.run(["git", "status", "--short", "tests"], cwd=run.ws, capture_output=True,
                               text=True).stdout.strip()
        outcomes = [g.outcome for g in run.groups]
        prs = sum(1 for o in outcomes if o == "pr")
        if m.truth == "heal":
            ok = bool(run.groups) and all(o == "pr" for o in outcomes) and bool(branches)
        else:
            ok = bool(run.groups) and all(o == "issue" for o in outcomes) and not branches and not dirty
        verdicts = [g.verdict.line() for g in run.groups]
        rows.append({"mutation": m.id, "truth": m.truth, "ok": ok, "prs": prs, "outcomes": outcomes,
                     "verdicts": verdicts, "seconds": round(secs, 1)})
        print(f"{'PASS' if ok else 'FAIL'} {m.id:22} {m.truth:11} {outcomes} {verdicts[0] if verdicts else ''} "
              f"({secs:.0f}s)", flush=True)
    passed = sum(r["ok"] for r in rows)
    wrong_heals = sum(1 for r in rows if r["truth"] != "heal" and r["prs"])
    missed = sum(1 for r in rows if r["truth"] == "heal" and not r["ok"])
    md = ["# Agent scorecard (full Strands agent, every mutation)", "",
          f"Correct outcome: **{passed}/{len(rows)}**. Wrong heals (PR on a non-healable): **{wrong_heals}**. "
          f"Healable cases not healed: **{missed}**.", ""]
    if name != "local":
        md += [f"Decider backend: **{name}** (hosted decider-cloud). Thresholds were calibrated on the local model.", ""]
    md += ["| Mutation | Truth | Outcome | Decision | OK |", "|---|---|---|---|---|"]
    md += [f"| {r['mutation']} | {r['truth']} | {', '.join(r['outcomes'])} | `{r['verdicts'][0] if r['verdicts'] else ''}` "
           f"| {'yes' if r['ok'] else '**no**'} |" for r in rows]
    (ROOT / "results" / f"AGENT_SCORECARD{sfx.upper()}.md").write_text("\n".join(md) + "\n")
    (ROOT / "results" / f"agent_scorecard{sfx}.json").write_text(json.dumps(rows, indent=1))
    print("\n".join(md[:3]))


if __name__ == "__main__":
    main()
