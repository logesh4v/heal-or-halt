# REUSABLE DECISION PATTERN: `policy-can-heal`

**Pattern tag:** `#policy`. One sharp yes/no gates a risky write action; one choice routes the
refusal; code, not the model, turns the confidence into act / ask / refuse.

## Files

| File | What it is |
|---|---|
| `question.json` | The two typed Decider questions: `can_heal` (noul) and `halt_reason` (choice: developer, platform, test_author) |
| `handler.py` | `failure_kind()` pre-filter, `decide()` pure policy, `ask_decider()` client, `make_gate()` Strands `InterventionHandler` |
| `thresholds.md` | The bands, the hard rules and how τ = 0.73 was chosen |

## Use it in your own agent

```python
from handler import make_gate          # copy this folder into your project
from strands import Agent

agent = Agent(model=..., tools=[..., open_pr], interventions=[make_gate(guarded_tool="open_pr")])
agent.state.set("failure", {"state": {...}, "old_name": "Split bill",
                            "new_name": "Calculate shares", "rerun_green": True})
```

The state Decider reads has five short fields (keep it under ~500 tokens):
`step`, `locator`, `error`, `a11y_diff` ('-' old / '+' new aria-snapshot lines), `commit`.
`hoh/collect.py` builds it from a real Playwright failure.

Run Decider locally first: `strands-decider serve <checkpoint> --device mlx --port 8099 --strict-window`
(binds 127.0.0.1; the server has no authentication, so keep it on loopback).

## Reuse it for something other than tests

Keep the shape and rewrite the two questions:
1. a yes/no that is TRUE only when the risky action is clearly safe,
2. a choice that names who handles the refusal,
3. three bands in code, with a calibrated top threshold,
4. a hard verification step the model cannot skip (here: the green re-run).
