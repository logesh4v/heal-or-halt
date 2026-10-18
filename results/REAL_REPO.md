# Heal or Halt on a real open-source app: TodoMVC

Run on 18 Oct 2026 (IST) on a MacBook Air M4, 16 GB. Reproduce with `make serve`, then `make todomvc`.

## What was tested

- **App:** [tastejs/todomvc](https://github.com/tastejs/todomvc), `examples/javascript-es5/dist`, pinned at
  commit `ff43b02` (MIT licence). It is cloned at run time; no TodoMVC code is committed to this repo.
  TodoMVC is the app Playwright itself uses for its official demo tests.
- **Tests:** 4 Playwright tests in `examples/todomvc/tests/`, ported to Python from TodoMVC's `app-spec.md`
  and Playwright's own TodoMVC demo spec. They are green on upstream TodoMVC 10 out of 10 runs.
- **Agent:** the same `python -m hoh run` used everywhere else. Same Decider model, same thresholds,
  same Nova models, same HealGate. Nothing was retuned for TodoMVC.
- **Breakages:** 4 developer commits on top of upstream, with the expected answer written down in
  `examples/todomvc/build_cases.py` **before** any run.

## Results

| Commit | What changed | Expected | Decider | What the agent did | Right? |
|---|---|---|---|---|---|
| `copy: friendlier input placeholder` | Input placeholder "What needs to be done?" became "Add a task" | Heal | 0.91, HEAL | Changed one locator line, re-ran the suite (green), opened a PR | Yes |
| `refactor: tidy item counter` | Off-by-one bug: "2 items left" shows 3 | Halt, developer | 0.71, HALT (assertion) | No code changed; issue for the developer | Yes |
| `copy + counter refactor` | The rename **and** the counter bug | Halt, developer | 0.90, HEAL | Fixed the locator, re-run still red (counter), undid the edit, issue for the developer | Yes |
| `copy: shorter clear button` | "Clear completed" became "Clear done" | Heal | 0.77, HEAL | Gate refused the agent's guess "Clear"; issue for the test author | Safe miss |

**4 commits, 0 wrong heals.** 3 handled exactly as expected; 1 real rename was sent to a person instead of
healed. One PR, three issues. Full logs and receipts are written to `examples-run/todomvc/cases/*/`.

## What the real app found that SplitPay never did

1. **A guessed heal that would have passed.** The "Clear" button is only shown after a todo is completed,
   so the page's first-load accessibility snapshot did not change and the evidence held no new name.
   Decider still said 0.77 (heal), and the agent guessed "Clear". That guess **passed the re-run**,
   because Playwright matches button names by substring and "Clear" matches "Clear done". The PR would have
   been green and wrong in spirit: a looser locator nobody asked for.
   **Fix (now in `hoh/agent.py`):** the gate only allows a new name that appears on a `+` line of the
   evidence. Regression test: `tests/test_gate.py::test_new_name_must_be_on_a_plus_line_of_the_evidence`.
   The 34-case scorecard was re-run after the change: still 34/34, 0 wrong heals.
2. **The test server dropped scripts.** Python's stdlib HTTP server queues only 5 connections. TodoMVC loads
   8 scripts at once, so about 1 run in 5 lost a script, the app failed to start, and a healthy app looked
   broken. The listen queue is now 64 (`tests/conftest.py`, `hoh/baseline.py`).
3. **`hoh run` assumed one HTML file and one test file.** It now snapshots the whole `app/` folder at the base
   commit and heals across every `tests/test_*.py` file. SplitPay behaves exactly as before
   (`make demo` 5/5 again, same table as the README).

## Honest limits of this run

- 4 cases on one app is a smoke test, not a benchmark. The 34-case scorecard and the 48-failure held-out
  eval on SplitPay are still the main evidence.
- The repo layout `hoh run` expects (`app/` + `tests/` with this project's `conftest.py`) is still required;
  a stock repo with its own test harness would need an adapter.
- The model writes the issue's prose. In the "Clear done" case the prose wrongly says the new button is
  "Clear"; every fact in the receipt below the prose is inserted by code and is correct.
