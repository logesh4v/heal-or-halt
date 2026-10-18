"""Question-design lab: try decomposed yes/no questions on the CALIBRATION mutations only.

The test split is never looked at here, so the held-out number stays honest.
"""

from __future__ import annotations

import json
import sys

from hoh.collect import ROOT
from hoh.eval import CASES, split_by_mutation

sys.path.insert(0, str(ROOT / "patterns" / "policy-can-heal"))
import urllib.request  # noqa: E402

CANDIDATES = {
    "replaced": {
        "type": "noul",
        "instructions": "In a11y_diff, '-' lines are the old page and '+' lines the new page. Is there a '+' line "
                        "that is a working replacement for the control the test was looking for: same kind of "
                        "control, new name or new position?",
        "criteria": {
            "true": "a '+' line shows the same kind of control under a different name or in a different place",
            "false": "the control only disappeared (a '-' line with no replacement), or it reappears marked "
                     "[disabled], or the diff shows no change, or the page is an error page or did not load",
        },
    },
    "broken": {
        "type": "noul",
        "instructions": "Does the evidence show that the app or its environment is broken, rather than just "
                        "reworded or rearranged?",
        "criteria": {
            "true": "an error page, a page that did not load, a control that was removed, hidden or disabled, "
                    "or a wrong value",
            "false": "every control is still present and usable, only with new wording or in a new place",
        },
    },
    "unchanged": {
        "type": "noul",
        "instructions": "Is the page exactly the same as before, so the test's own locator must be wrong?",
        "criteria": {"true": "a11y_diff says (no change)", "false": "a11y_diff lists changed lines"},
    },
}


def ask(state, questions):
    body = json.dumps({"state": state, "questions": questions}).encode()
    req = urllib.request.Request("http://127.0.0.1:8099/v1/systemone", data=body,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        return json.loads(r.read())["answers"]


def main():
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    plain = [r for r in rows if r["truth"] != "combo"]
    cal_m, _ = split_by_mutation(plain)
    cal = [r for r in plain if r["mutation"] in cal_m]
    out = []
    for r in cal:
        a = ask(r["state"], CANDIDATES)
        out.append({"m": r["mutation"], "t": r["truth"], **{k: round(v["noul"], 2) for k, v in a.items()}})
        print(f"{r['mutation']:22} {r['truth']:11} " + " ".join(f"{k}={v['noul']:.2f}" for k, v in a.items()), flush=True)
    (ROOT / "results" / "question_lab_cal.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
