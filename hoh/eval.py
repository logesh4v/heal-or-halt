"""Eval: Decider 2B vs a deterministic rule vs Amazon Nova Micro on the Mutation Monkey cases.

Ground truth comes from the mutation, never from a model. Combo cases (rename + real bug in
one commit) are reported apart: per failure the rename really is healable, and it is the
re-run gate, not the classifier, that has to catch the hidden bug.

    .venv/bin/python -m hoh.eval            (needs `make serve`; Bedrock via AWS_PROFILE)
    .venv/bin/python -m hoh.eval --no-llm   (skip the Nova Micro baseline)

Writes results/eval.json and results/EVAL.md.
"""

from __future__ import annotations

import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path

from hoh.collect import ROOT

sys.path.insert(0, str(ROOT / "patterns" / "policy-can-heal"))
from handler import ASK, HEAL, QUESTIONS, ask_decider, decide, failure_kind  # noqa: E402

CASES = ROOT / "eval" / "cases.jsonl"
OUT_JSON = ROOT / "results" / "eval.json"
OUT_MD = ROOT / "results" / "EVAL.md"
NOVA_MICRO = os.environ.get("HOH_BASELINE_MODEL", "us.amazon.nova-micro-v1:0")
ALPHA = float(os.environ.get("HOH_ALPHA", "0.05"))  # target expected wrong-heal rate
SEED = 7
ROLE = re.compile(r'^[-+]\s*-\s*(\w+)')


def rule_baseline(state: dict) -> bool:
    """A careful rename rule: every removed node has an added node of the same role, nothing else."""
    diff = state["a11y_diff"]
    if diff == "(no change)" or "page failed to load" in diff:
        return False
    minus = [ROLE.match(l).group(1) for l in diff.splitlines() if l.startswith("-") and ROLE.match(l)]
    plus = [ROLE.match(l).group(1) for l in diff.splitlines() if l.startswith("+") and ROLE.match(l)]
    return bool(minus) and sorted(minus) == sorted(plus)


def nova_baseline(client, state: dict) -> tuple[bool | None, float, int, int]:
    q = QUESTIONS["can_heal"]
    prompt = (f"{q['instructions']}\nYES means: {q['criteria']['true']}\nNO means: {q['criteria']['false']}\n\n"
              f"Failure:\n{json.dumps(state, ensure_ascii=False, indent=1)}\n\nAnswer with exactly YES or NO.")
    t = time.perf_counter()
    out = client.converse(modelId=NOVA_MICRO, messages=[{"role": "user", "content": [{"text": prompt}]}],
                          inferenceConfig={"maxTokens": 5, "temperature": 0})
    ms = (time.perf_counter() - t) * 1000
    text = out["output"]["message"]["content"][0]["text"].strip().upper()
    ans = True if text.startswith("YES") else False if text.startswith("NO") else None
    return ans, ms, out["usage"]["inputTokens"], out["usage"]["outputTokens"]


def split_by_mutation(rows: list[dict]) -> tuple[set[str], set[str]]:
    """Held-out split by MUTATION (a mutation's failures never straddle the split), per truth class."""
    rng = random.Random(SEED)
    cal, test = set(), set()
    by_truth: dict[str, list[str]] = {}
    for r in rows:
        by_truth.setdefault(r["truth"], [])
        if r["mutation"] not in by_truth[r["truth"]]:
            by_truth[r["truth"]].append(r["mutation"])
    for muts in by_truth.values():
        rng.shuffle(muts)
        half = len(muts) // 2
        cal |= set(muts[:half])
        test |= set(muts[half:])
    return cal, test


def conformal_tau(cal: list[dict], alpha: float) -> float:
    """Conformal risk control (Angelopoulos et al., ICLR 2024) for loss = 1[heal proposed on a non-healable].

    Pick the smallest threshold whose adjusted calibration risk  n/(n+1)*R_hat + 1/(n+1)  <= alpha.
    The loss is monotone (non-increasing) in the threshold, which is what the guarantee needs.
    """
    n = len(cal)
    for tau in [round(0.50 + 0.01 * i, 2) for i in range(50)]:
        risk = sum(1 for r in cal if r["p"] >= tau and r["truth"] != "heal") / n
        if n / (n + 1) * risk + 1 / (n + 1) <= alpha:
            return tau
    return 0.99


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def main() -> None:
    use_llm = "--no-llm" not in sys.argv
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    client = None
    if use_llm:
        import boto3
        client = boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "default")).client(
            "bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    for r in rows:
        s = r["state"]
        r["kind"] = failure_kind(s["error"])
        t = time.perf_counter()
        a = ask_decider(s)
        r["decider_ms"] = (time.perf_counter() - t) * 1000
        r["p"] = a["can_heal"]["noul"]
        r["halt_reason"] = a["halt_reason"]["choice"]
        r["rule"] = rule_baseline(s)
        if client:
            r["llm"], r["llm_ms"], r["llm_in"], r["llm_out"] = nova_baseline(client, s)
        print(f"{r['mutation']:22} {r['truth']:11} kind={r['kind']:10} p={r['p']:.2f} "
              f"rule={'H' if r['rule'] else '-'} llm={r.get('llm')}", flush=True)

    plain = [r for r in rows if r["truth"] != "combo"]
    cal_m, test_m = split_by_mutation(plain)
    cal = [r for r in plain if r["mutation"] in cal_m and r["kind"] == "locator"]
    test = [r for r in plain if r["mutation"] in test_m]
    tau = conformal_tau(cal, ALPHA)

    def classifier_stats(rs: list[dict], pred) -> dict:
        tp = sum(1 for r in rs if pred(r) and r["truth"] == "heal")
        fp = sum(1 for r in rs if pred(r) and r["truth"] != "heal")
        pos = sum(1 for r in rs if r["truth"] == "heal")
        neg = len(rs) - pos
        acc = sum(1 for r in rs if bool(pred(r)) == (r["truth"] == "heal")) / len(rs)
        return {"healed": f"{tp}/{pos}", "wrong_heals": f"{fp}/{neg}", "accuracy": round(acc, 3)}

    def policy(r, t):  # full pipeline: pre-filter + bands (gray zone counts as "not healed automatically")
        return decide({"can_heal": {"noul": r["p"]}, "halt_reason": {"choice": r["halt_reason"]}},
                      kind=r["kind"], heal=t, ask=min(ASK, t), rerun_green=True,
                      a11y_diff=r["state"]["a11y_diff"]).action == "heal"

    owner_rows = [r for r in plain if r["truth"] in ("developer", "platform", "test_author")]
    owner_acc = sum(1 for r in owner_rows if (decide({"can_heal": {"noul": r["p"]}, "halt_reason": {"choice": r["halt_reason"]}},
                                                     kind=r["kind"], a11y_diff=r["state"]["a11y_diff"]).halt_reason == r["truth"])) / len(owner_rows)
    gray = [r for r in test if r["kind"] == "locator" and min(ASK, tau) <= r["p"] < tau]
    res = {
        "n_cases": len(rows), "n_mutations": len({r["mutation"] for r in rows}),
        "split": {"calibration_mutations": len(cal_m), "test_mutations": len(test_m), "test_cases": len(test)},
        "alpha": ALPHA, "tau_conformal": tau,
        "test_split": {
            "decider_policy_tau": classifier_stats(test, lambda r: policy(r, tau)),
            "decider_policy_0.70": classifier_stats(test, lambda r: policy(r, 0.70)),
            "decider_policy_shipped": classifier_stats(test, lambda r: policy(r, HEAL)),
            "decider_raw_0.50": classifier_stats(test, lambda r: r["p"] >= 0.5),
            "rule_baseline": classifier_stats(test, lambda r: r["rule"]),
            **({"nova_micro": classifier_stats(test, lambda r: r["llm"] is True)} if client else {}),
            "gray_zone_to_human": len(gray),
        },
        "all_cases_policy_0.70": classifier_stats(plain, lambda r: policy(r, 0.70)),
        "halt_owner_accuracy": round(owner_acc, 3),
        "combo": [{"mutation": r["mutation"], "step": r["state"]["step"], "p": round(r["p"], 3)}
                  for r in rows if r["truth"] == "combo"],
        "latency_ms": {"decider_p50": round(statistics.median(r["decider_ms"] for r in rows)),
                       "decider_p95": round(pct([r["decider_ms"] for r in rows], 0.95))},
        "p_by_truth": {t: [round(min(r["p"] for r in rows if r["truth"] == t), 2),
                           round(max(r["p"] for r in rows if r["truth"] == t), 2)]
                       for t in sorted({r["truth"] for r in rows})},
    }
    if client:
        res["latency_ms"] |= {"nova_micro_p50": round(statistics.median(r["llm_ms"] for r in rows)),
                              "nova_micro_p95": round(pct([r["llm_ms"] for r in rows], 0.95))}
        res["nova_micro_tokens"] = {"input": sum(r["llm_in"] for r in rows), "output": sum(r["llm_out"] for r in rows),
                                    "unparsed": sum(1 for r in rows if r["llm"] is None)}
    OUT_JSON.parent.mkdir(exist_ok=True)
    OUT_JSON.write_text(json.dumps({"summary": res, "rows": [
        {k: r.get(k) for k in ("mutation", "truth", "kind", "p", "halt_reason", "rule", "llm", "decider_ms", "llm_ms")}
        for r in rows]}, ensure_ascii=False, indent=1))
    lines = ["# Heal or Halt eval", "", f"{res['n_cases']} real failures from {res['n_mutations']} mutations. "
             f"Held-out split by mutation: {len(cal_m)} calibration / {len(test_m)} test mutations "
             f"({len(test)} test cases).", "",
             f"Conformal threshold for alpha={ALPHA}: tau={tau}", "",
             "| Test split | Healable healed | Wrong heals | Accuracy |", "|---|---|---|---|"]
    for k, v in res["test_split"].items():
        if isinstance(v, dict):
            lines.append(f"| {k} | {v['healed']} | {v['wrong_heals']} | {v['accuracy']} |")
    lines += ["", f"Gray zone (sent to a human) on the test split: {res['test_split']['gray_zone_to_human']}",
              f"Halt owner routing accuracy (all non-heal cases): {res['halt_owner_accuracy']}",
              f"Latency: {res['latency_ms']}", f"p(can_heal) range by truth: {res['p_by_truth']}",
              f"Combo cases (must be caught by the re-run gate): {res['combo']}"]
    if client:
        lines.append(f"Nova Micro tokens: {res['nova_micro_tokens']}")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
