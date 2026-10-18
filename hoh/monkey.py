"""Mutation Monkey: break SplitPay (or its tests) in seeded, labelled ways and collect real failures.

Every mutation carries its ground truth, so the eval set needs no hand labelling:
    heal         the control still exists, only renamed / re-labelled / moved
    developer    the app is really broken (wrong maths, control removed or disabled ...)
    platform     the environment failed (server down, 500, too slow)
    test_author  the test itself is wrong (locator typo, wrong role ...)
    combo        rename AND a real bug in one commit (agent demo: heal must fail its re-run)

Run:  .venv/bin/python -m hoh.monkey            -> eval/cases.jsonl
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from hoh.collect import ROOT

APP = (ROOT / "demo-app" / "index.html").read_text()
TESTS = ROOT / "tests"
OUT = ROOT / "eval" / "cases.jsonl"
BTN = '<button id="split" type="submit">Split bill</button>'


@dataclass
class Mutation:
    id: str
    truth: str                      # heal | developer | platform | test_author | combo
    commit: str
    app: list[tuple[str, str]] = field(default_factory=list)    # (old, new) replacements in index.html
    tests: list[tuple[str, str]] = field(default_factory=list)  # (old, new) in test_splitpay_e2e.py
    mode: str = "normal"

    def build_app(self) -> str:
        html = APP
        for old, new in self.app:
            assert old in html, f"{self.id}: '{old}' not in app"
            html = html.replace(old, new)
        return html


def rename_button(name: str) -> tuple[str, str]:
    return (BTN, BTN.replace(">Split bill<", f">{name}<"))


MUTATIONS: list[Mutation] = [
    # ---- heal: same control, new name / label / place ----
    *[Mutation(f"btn-rename-{i}", "heal", f"copy: rename main action to '{n}'", [rename_button(n)])
      for i, n in enumerate(["Calculate shares", "Divide the bill", "Share the cost", "Work it out",
                             "Get each share", "Calculate", "Go", "Split it up now"])],
    *[Mutation(f"total-label-{i}", "heal", f"copy: total field label is now '{n}'",
               [('<label for="total">Bill total (₹)</label>', f'<label for="total">{n}</label>')])
      for i, n in enumerate(["Total amount (₹)", "Amount to split (₹)", "Grand total (₹)"])],
    *[Mutation(f"people-label-{i}", "heal", f"copy: people field label is now '{n}'",
               [('<label for="people">Number of people</label>', f'<label for="people">{n}</label>')])
      for i, n in enumerate(["How many people?", "Party size", "Split between"])],
    Mutation("btn-to-input", "heal", "refactor: submit is an input element now",
             [(BTN, '<input id="split" type="submit" value="Calculate shares">')]),
    Mutation("btn-aria-label", "heal", "a11y: give the main action a descriptive accessible name",
             [(BTN, '<button id="split" type="submit" aria-label="Compute everyone\'s share">Split bill</button>')]),
    Mutation("btn-move-top", "heal", "layout: move the main action above the fields and rename it",
             [(BTN, ""), ('<label for="total">', '<button id="split" type="submit">Calculate shares</button>\n      <label for="total">')]),
    Mutation("btn-move-wrap", "heal", "layout: action row container, label 'Split now'",
             [(BTN, '<div class="actions"><span>Ready?</span><button id="split" type="submit">Split now</button></div>')]),
    # ---- developer: the product is really broken ----
    Mutation("math-multiply", "developer", "refactor: move share calculation into a helper",
             [("(total / people)", "(total * people)")]),
    Mutation("math-floor", "developer", "perf: integer maths for shares",
             [("Math.round((total / people) * 100) / 100", "Math.floor(total / people)")]),
    Mutation("js-crash", "developer", "feat: currency formatting helper",
             [("const share =", "const share = formatINR(")]),
    Mutation("btn-disabled", "developer", "feat: disable split until terms are accepted",
             [(BTN, BTN.replace('type="submit"', 'type="submit" disabled'))]),
    Mutation("btn-removed", "developer", "cleanup: remove unused form controls",
             [(BTN, "")]),
    Mutation("btn-hidden", "developer", "style: hide action on narrow layouts",
             [(BTN, BTN.replace('type="submit"', 'type="submit" style="display:none"'))]),
    Mutation("people-input-removed", "developer", "feat: default to splitting between 2 people",
             [('<input id="people" name="people" type="number" min="1" step="1" required>', "")]),
    Mutation("submit-noop", "developer", "refactor: button no longer submits the form",
             [('type="submit">Split bill', 'type="button">Split bill')]),
    # ---- platform: the environment failed ----
    Mutation("server-down", "platform", "chore: bump dependencies", mode="down"),
    Mutation("server-500", "platform", "chore: bump dependencies", mode="error500"),
    Mutation("server-slow", "platform", "chore: bump dependencies", mode="slow"),
    # ---- test_author: the test is wrong, the app is fine ----
    Mutation("test-typo-button", "test_author", "test: tidy helpers",
             tests=[('name="Split bill"', 'name="Splt bill"')]),  # "Split bil" still substring-matches!
    Mutation("test-typo-label", "test_author", "test: tidy helpers",
             tests=[('get_by_label("Bill total (₹)")', 'get_by_label("Bill totl (₹)")')]),
    Mutation("test-wrong-role", "test_author", "test: tidy helpers",
             tests=[('get_by_role("button", name="Split bill")', 'get_by_role("link", name="Split bill")')]),
    Mutation("test-wrong-expect", "test_author", "test: tidy helpers",
             tests=[("₹300.00", "₹301.00")]),
    # ---- combo: a rename hides a real bug in the same commit ----
    Mutation("combo-rename-math", "combo", "feat: new wording and a share helper",
             [rename_button("Calculate shares"), ("(total / people)", "(total * people)")]),
]


def run_mutation(m: Mutation, work: Path, timeout_ms: int = 2000) -> list[dict]:
    ws = work / m.id
    shutil.rmtree(ws, ignore_errors=True)
    (ws / "app").mkdir(parents=True)
    (ws / "failures").mkdir()
    shutil.copytree(TESTS, ws / "tests", ignore=shutil.ignore_patterns("__pycache__", "test_policy_bands.py", "test_gate.py", "test_cli.py"))
    shutil.copy(ROOT / "pytest.ini", ws / "pytest.ini")
    (ws / "app" / "index.html").write_text(m.build_app())
    test_file = ws / "tests" / "test_splitpay_e2e.py"
    src = test_file.read_text()
    for old, new in m.tests:
        assert old in src, f"{m.id}: '{old}' not in tests"
        src = src.replace(old, new)
    test_file.write_text(src)
    env = {**os.environ, "HOH_ROOT": str(ROOT), "HOH_APP_DIR": str(ws / "app"), "HOH_APP_MODE": m.mode,
           "HOH_FAILURES_DIR": str(ws / "failures"), "HOH_COMMIT": m.commit, "HOH_TIMEOUT_MS": str(timeout_ms)}
    subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "tests"], cwd=ws, env=env,
                   capture_output=True, text=True, timeout=300)
    rows = []
    for f in sorted((ws / "failures").glob("*.json")):
        rec = json.loads(f.read_text())
        rows.append({"mutation": m.id, "truth": m.truth, **rec})
    return rows


def main() -> None:
    work = Path(os.environ.get("KIROCREW_SCRATCH", "/tmp")) / "hoh-monkey"
    only = set(sys.argv[1:])
    rows: list[dict] = []
    for m in MUTATIONS:
        if only and m.id not in only:
            continue
        got = run_mutation(m, work)
        print(f"{m.id:22} {m.truth:12} failures={len(got)}", flush=True)
        rows.extend(got)
    OUT.parent.mkdir(exist_ok=True)
    if only and OUT.exists():  # partial re-run: replace just those mutations' rows
        kept = [json.loads(ln) for ln in OUT.read_text().splitlines() if ln.strip()]
        rows = [r for r in kept if r["mutation"] not in only] + rows
    with OUT.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} cases to {OUT}")


if __name__ == "__main__":
    main()
