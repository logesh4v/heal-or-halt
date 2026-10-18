# Thresholds for `policy-can-heal`

| Band | `can_heal` | Action |
|---|---|---|
| Heal | ≥ **0.73** | apply the fix, re-run, open a PR only if green |
| Ask | 0.55 – 0.73 | Nova Pro second opinion (veto only), then a human |
| Halt | < 0.55 | no code change, issue for `halt_reason`'s owner |

Hard rules that run regardless of the number: an assertion failure is never healed, a page that
did not load goes to platform, a new name that still contains the old one is rejected, a fix
without a green re-run is never merged, and an agent that hits the gate 3 times is locked out.

## How 0.73 was chosen

Conformal risk control (Angelopoulos et al., *Conformal Risk Control*, ICLR 2024,
arXiv:2208.02814) with loss = 1[heal proposed on a non-healable failure] and target α = 0.05:
the smallest τ with `n/(n+1)·R̂(τ) + 1/(n+1) ≤ α` on the calibration split.

- Data: 97 real failures from 34 Mutation Monkey mutations (`eval/cases.jsonl`).
- Split by **mutation**, stratified by truth class (seed 7): 16 calibration, 17 test mutations.
  A mutation's failures never appear on both sides.
- Calibration: 36 locator failures, 9 of them non-healable. α=0.20 → 0.53, α=0.10 → 0.63, α=0.05 → **0.73**.
- With n = 36 the bound carries real small-sample slack; treat it as a guide, not a certificate.

Full numbers: `results/EVAL.md`. Re-run: `make serve` then `make eval`.

## If you change the question wording

Re-run `make monkey eval`. Question v1 ("Does the element still exist ... with the app otherwise
working?") wrongly healed removed, hidden and disabled controls (5/21 wrong heals on the test
split, `results/EVAL_v1_question.md`). v2 asks for a '+' replacement line explicitly and was
tuned on the calibration mutations only (`hoh/question_lab.py`).
