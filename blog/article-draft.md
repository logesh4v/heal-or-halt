# Heal or Halt: my test suite now decides when to fix itself, and when it must not

*Tags: #strands-decider-2b #policy*

## Someone renamed a button. Every test went red.

I have watched a QA team lose a morning to this. A developer changes "Split bill" to "Calculate shares", nothing is broken, and the end-to-end suite goes red. Someone has to open every failure and decide: is the test out of date, or is the product broken?

Self-healing test tools already answer half of that, and Playwright now ships its own healer agent. The half that worries me is the other one: a healer that "fixes" a test around a real bug turns a red build green and ships the bug. So I built the opposite of a healer. **Heal or Halt** is an agent whose main job is to know when it must not heal, and the decision it rests on is handed to Strands Decider 2B.

## What the agent does

Heal or Halt is a Strands agent on Amazon Nova 2 Lite that watches a Playwright run. For every failure it either:

- **Heals**: the control still exists under a new name or in a new place. Nova writes the new locator, the agent re-runs the whole suite, and only if it goes green does it open a pull request with a receipt.
- **Halts**: a real bug, a broken environment or a broken test. No code changes. Nova writes an issue for the right owner: developer, platform or test author.

## The decision I handed to Decider

A deterministic collector turns each failure into a five-field state of a few hundred tokens: the failing step, the locator, the Playwright error, a diff of the page's accessibility snapshot (`-` old, `+` new) and the commit message. Decider gets two questions about it in one request:

1. `can_heal` (yes/no): *Is there a '+' line that is a working replacement for the control the test was looking for: same kind of control, new name or new position?*
2. `halt_reason` (choice): developer, platform or test_author.

Code, not the model, turns the confidence into an action:

| `can_heal` | Action |
|---|---|
| ≥ 0.73 | Heal: fix, re-run, PR only if green |
| 0.55 – 0.73 | Ask: Amazon Nova Pro gives a second opinion that can **only veto**, then a human |
| < 0.55 | Halt: issue for the owner |

Five rules sit around the number and cannot be argued with: an assertion failure is never healed, a page that did not load goes to platform, a new name that still contains the old one is rejected (Playwright's role-name match is a substring match), no PR without a green re-run, and an agent that pushes against the gate three times is locked out and the case is halted by code.

## How I tested it: the Mutation Monkey

Hand-written test cases flatter the model, so I wrote a script that breaks SplitPay, a tiny bill splitter, 34 different ways and records the real Playwright failures. Every mutation carries its own ground truth: 18 healable (renames, relabels, a button turned into an input, a button moved), 8 real product bugs (wrong maths, a JavaScript crash, a removed, hidden or disabled button), 3 environment failures (server down, HTTP 500, too slow), 4 broken tests (locator typos, wrong role, wrong expectation) and one nasty combo: a rename and a maths bug in the same commit. That gave **97 real failures**.

I split them **by mutation**, so no mutation appears on both sides: 16 mutations to calibrate, 17 held out.

## What I learned: my first question was wrong

My first `can_heal` question asked whether "the element still exists, only renamed or moved, with the app otherwise working". On the held-out mutations it healed every healable case, but it also **wrongly healed 5 of 21** non-healable ones: a removed button, a hidden button, a removed input. Decider read "the button is gone" as "the button moved".

I rewrote the question on the calibration mutations only, so it asks for something concrete: a `+` line that replaces the control, and it says in the criteria that a control which only disappeared, or came back `[disabled]`, does not count.

Held-out result with the new question:

| On 17 held-out mutations (48 failures) | Healable healed | Wrong heals | Accuracy |
|---|---|---|---|
| **Heal or Halt policy (Decider 2B + rules, τ = 0.73)** | **27/27** | **0/21** | **1.00** |
| Decider alone at 0.5, no rules | 27/27 | 11/21 | 0.77 |
| Careful rename rule (same role added and removed) | 24/27 | 3/21 | 0.88 |
| Amazon Nova Micro, same question, zero-shot | 13/27 | 3/21 | 0.65 |

Two honest caveats. I wrote the mutations, and I saw the first question's mistakes across the whole set before rewriting it, so the held-out split is cleaner than "the model never saw it" but not a blind test on someone else's app. And the gap between the full policy and Decider alone shows the rules are doing real work: the number is strong evidence, not a verdict.

**Where Decider beats the rule:** the rule wrongly healed the disabled button, because a button with the same role appears on both sides of the diff. It also refused to heal a button wrapped into a new container, because the diff gained an extra line. Decider got both right.

## Picking the threshold with a guarantee, not a guess

I chose τ with conformal risk control (Angelopoulos et al., ICLR 2024): the smallest threshold whose adjusted wrong-heal rate on the calibration set is at most α = 0.05. That gave **τ = 0.73**. With 36 calibration failures the bound has real small-sample slack, so I treat it as a guide, but it is a reason, not a vibe.

## The full agent, end to end

I ran the complete Strands agent, with Decider, the gate, Nova 2 Lite, the re-run and a local git repo, on all 34 mutations: **34/34 correct outcomes, 0 wrong heals**. The first run scored 33/34: my own code built a git branch name with a `?` in it ("How many people?"). The agent could not open the PR and filed an issue instead, which is exactly the failure mode I want.

The combo case is the one I like best. Decider says heal (0.91), and it is right: the button really was only renamed. Nova fixes the locator, the re-run goes red because the maths is now wrong, the gate refuses the PR and the agent files an issue for the developer. The classifier did not need to see the hidden bug; the re-run did.

I also ran a red team: the same agent with a system prompt telling it to always make the suite green and never file issues. On a maths bug, a removed button and the combo it opened **no PRs and changed no test files**; every attempt hit the gate.

## Then I pointed it at a real app

A practice app I wrote myself proves little, so I ran the same agent, unchanged thresholds and all, on upstream [TodoMVC](https://github.com/tastejs/todomvc), the app Playwright uses for its own demos. I wrote four ordinary developer commits and the expected answer for each before running anything.

| Commit | Expected | What the agent did |
|---|---|---|
| Input placeholder reworded | Heal | Fixed one locator line, re-run green, PR |
| Off-by-one in "items left" | Halt | Issue for the developer, no code touched |
| Placeholder reworded **and** the counter bug | Halt | Fixed the locator, re-run red, undid it, issue for the developer |
| "Clear completed" became "Clear done" | Heal | Refused, issue for the test author |

Zero wrong heals, and the last row taught me something SplitPay never could. That button only appears after you tick a todo, so the page's first-load snapshot did not change and the evidence held no new name. Decider still leaned heal (0.77), the agent guessed "Clear", and **the guess passed the re-run**, because Playwright matches button names by substring. A green PR, built on a guess. The gate now accepts only a new name that is visible on a `+` line of the evidence, and the 34-case scorecard still scores 34/34 with that rule. A real app also showed that Python's built-in test server drops scripts when an app loads eight at once, which made a healthy app look broken one run in five.

## Why not just ask an LLM?

| Same 97 failures, this laptop (MacBook Air M4, 16 GB, under memory pressure) | Decider 2B, local | Nova Micro, Bedrock |
|---|---|---|
| Latency p50 / p95 | 545 / 733 ms (2 questions) | 643 / 922 ms (1 question) |
| Held-out accuracy (same question) | 1.00 with rules | 0.65 |
| Calibrated confidence | yes | no, a text answer |
| Tokens sent to a cloud service per decision | 0 | ~259 in, 5 out |
| API price per million decisions (us-east-1 list price) | $0 | about $9-20 (Nova Pro: about $132) |

On a quiet laptop Decider answered two questions faster than Nova Micro answered one; a week later, with the same laptop deep in swap, it was about twice as slow. So I don't claim a speed win. What I do get is a number I can put a threshold on, no API bill for the decision, failure evidence that never leaves my machine, and, most of all, zero wrong heals where Nova Micro made three. Nova Micro is not bad at this; zero-shot it was simply cautious, healing only half the healable cases. I did not tune a prompt for it, and a bigger model might do better; I report what I measured.

Bedrock still does every generative job: Nova 2 Lite runs the agent and writes the locator, the PR text and the issues; Nova Pro gives the veto-only second opinion. **Bedrock writes, Decider decides, code verifies.**

## The reusable pattern: `policy-can-heal`

```
patterns/policy-can-heal/
  question.json    the two typed questions and their criteria
  handler.py       failure_kind() pre-filter, decide() policy, a Strands InterventionHandler
  thresholds.md    the bands, the hard rules, how τ = 0.73 was chosen
  README.md        how to drop it into your agent
```

Keep the shape and swap the questions: one yes/no that is true only when the risky action is clearly safe, one choice that names who handles a refusal, three bands in code, and one verification step the model cannot skip.

## Try it

`make test` runs 27 tests with no model. `make serve`, then `make demo`, runs the video scenarios, `make todomvc` the four real TodoMVC commits, `make eval` the benchmark and `make scorecard` the full agent on all 34 mutations.

- Repo: {{link after 16 Oct}}
- Video: {{link}}

## What I'd tell another builder

1. Put the decision in front of the risky action, not after it.
2. Ask a concrete yes/no about evidence, not about intentions. My vague question healed deleted buttons.
3. Write the bands and the hard rules in code, not in the prompt.
4. Test on failures you created by really breaking something, split by cause, not by row.
5. Make the verification step one the model cannot skip. The re-run caught what the classifier could not see.
