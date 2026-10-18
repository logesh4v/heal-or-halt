# Heal or Halt: my test suite now decides when to fix itself, and when it must not

*Tags: #strands-decider-2b #policy*

> **TL;DR.** Heal or Halt is a Strands agent that looks at every failing Playwright test and makes one call: heal it (the button was only renamed) or halt (a real bug, so file an issue for the right person). Strands Decider 2B makes that call on my laptop with a confidence number, Amazon Nova on Bedrock writes the fix or the issue, and plain code refuses any pull request until the re-run is green. On 48 held-out failures it healed 27/27 fixable ones with **0 wrong heals**; the full agent got **34/34** kinds of breakage right; and on four real commits to upstream TodoMVC it made **0 wrong heals**, after a real app showed me a hole my own app never could.
>
> Code: [github.com/logesh4v/heal-or-halt](https://github.com/logesh4v/heal-or-halt) · Video (2:49): [youtu.be/oHNKQBP5hpc](https://youtu.be/oHNKQBP5hpc)

## Someone renamed a button. Every test went red.

I have watched a QA team lose a morning to this. A developer changes "Split bill" to "Calculate shares", nothing is broken, and the end-to-end suite goes red. Someone has to open every failure and decide: is the test out of date, or is the product broken?

Self-healing test tools already answer half of that, and Playwright now ships its own healer agent. The half that worries me is the other one: a healer that "fixes" a test around a real bug turns a red build green and ships the bug. So I built the opposite of a healer. **Heal or Halt** is an agent whose main job is to know when it must not heal, and the decision it rests on is handed to Strands Decider 2B.

## What the agent does

Heal or Halt is a Strands agent on Amazon Nova 2 Lite that watches a Playwright run. For every failure it either:

- **Heals**: the control still exists under a new name or in a new place. Nova writes the new locator, the agent re-runs the whole suite, and only if it goes green does it open a pull request with a receipt.
- **Halts**: a real bug, a broken environment or a broken test. No code changes. Nova writes an issue for the right owner: developer, platform or test author.

> Bedrock writes, Decider decides, code verifies.

## Why Decider, and not just another LLM call

Strands Decider 2B is an open, experimental decision model from AWS with about 2 billion parameters. It does not generate text. You give it a state and a typed question, and it returns a choice, a yes or no, or a score, each with a calibrated confidence. The official Strands announcement reports a median of about 115 ms on an RTX 3090 and about 153 ms on a MacBook Pro M3.

That shape is exactly what a "may I touch this test?" gate needs. I don't want prose from the model that decides. I want a number I can put a threshold on, and a refusal I can route to the right person.

## Day 0: the first benchmarks

Before writing any agent code I wanted to know two things: can Decider run on my 16 GB MacBook Air M4 at all, and is it any good at this question?

**Which backend.** I ran the same states through Decider on Apple's MLX and on PyTorch's MPS backend, five repetitions each:

| 256-token state | MLX median | MPS median | MLX peak memory | MPS peak memory |
|---|---|---|---|---|
| 1 question | **360 ms** | 893 ms | 3.75 GiB | 4.3 GiB |
| 8 questions, shared prefix | **1,011 ms** | 2,865 ms | 4.19 GiB | 4.3 GiB |
| 8 questions, batched | 3,068 ms | 9,400 ms | 4.09 GiB | 5.35 GiB |

MLX was about 2.5 to 3 times faster and lighter, and asking several questions over one shared prefix beat batching them by about 3 times. Both gave the same answers (8/8). So: MLX, and one request with all my questions in it. Longer states cost real time (a 1,024-token state took 1.3 s for one question on MLX), which is why the collector keeps every state short.

**Which question.** On 25 hand-written failures, a five-way "what kind of failure is this?" question got only 15/25 right, so I dropped it. A plain yes/no `can_heal` question healed 10/10 healable cases with 0/15 wrong heals at a 0.70 cut. That looked great and proved nothing yet: I had picked the cut on the same 25 cases. Everything after this point was about earning that number honestly.

## The decision I handed to Decider

A deterministic collector turns each real failure into a five-field state of a few hundred tokens: the failing step, the locator, the Playwright error, a diff of the page's accessibility snapshot (`-` old, `+` new) and the commit message. Decider gets two questions about it in one request:

1. `can_heal` (yes/no): *Is there a '+' line that is a working replacement for the control the test was looking for: same kind of control, new name or new position?*
2. `halt_reason` (choice): developer, platform or test_author.

Code, not the model, turns the confidence into an action:

| `can_heal` | Action |
|---|---|
| ≥ 0.73 | Heal: fix, re-run, PR only if green |
| 0.55 – 0.73 | Ask: Amazon Nova Pro gives a second opinion that can **only veto**, then a human |
| < 0.55 | Halt: issue for the owner |

Hard rules sit around the number and cannot be argued with: an assertion failure is never healed, a page that did not load goes to platform, a new name that still contains the old one is rejected (Playwright's role-name match is a substring match), the new name must appear on a `+` line of the evidence, there is no PR without a green re-run, and an agent that pushes against the gate three times is locked out and the case is halted by code.

## How I broke it: the Mutation Monkey

Hand-written test cases flatter the model, so I wrote a script that breaks SplitPay, a tiny bill splitter, 34 different ways and records the real Playwright failures. Every mutation carries its own ground truth: 18 healable (renames, relabels, a button turned into an input, a button moved), 8 real product bugs (wrong maths, a JavaScript crash, a removed, hidden or disabled button), 3 environment failures (server down, HTTP 500, too slow), 4 broken tests (locator typos, wrong role, wrong expectation) and one nasty combo: a rename and a maths bug in the same commit. That gave **97 real failures**.

I split them **by mutation**, so no mutation appears on both sides: 16 mutations to calibrate, 17 held out (48 failures).

## My first question was wrong

My first `can_heal` question asked whether "the element still exists, only renamed or moved, with the app otherwise working". On the held-out mutations it healed every healable case, but it also **wrongly healed 5 of 21** non-healable ones: a removed button, a hidden button, a removed input. Decider read "the button is gone" as "the button moved".

I rewrote the question on the calibration mutations only, so it asks for something concrete: a `+` line that replaces the control. Its criteria say that a control which only disappeared, or came back `[disabled]`, does not count.

Held-out result with the new question:

| 17 held-out mutations (48 failures) | Healable healed | Wrong heals | Accuracy |
|---|---|---|---|
| **Heal or Halt policy (Decider 2B + rules, τ = 0.73)** | **27/27** | **0/21** | **1.00** |
| Decider alone at 0.5, no rules | 27/27 | 11/21 | 0.77 |
| Careful rename rule (same role added and removed) | 24/27 | 3/21 | 0.88 |
| Amazon Nova Micro, same question, zero-shot | 13/27 | 3/21 | 0.65 |

Two honest caveats. I wrote the mutations, and I saw the first question's mistakes across the whole set before rewriting it, so the held-out split is cleaner than "the model never saw it" but not a blind test on someone else's app. And the gap between the full policy and Decider alone shows the rules are doing real work: the model and the rules together are the product, not either one alone.

**Where Decider beat the rule:** the rule wrongly healed the disabled button, because a button with the same role appears on both sides of the diff. It also refused to heal a button wrapped in a new container, because the diff gained an extra line. Decider got both right.

## Picking the threshold with a guarantee, not a guess

I chose τ with conformal risk control (Angelopoulos et al., *Conformal Risk Control*, ICLR 2024): the smallest threshold whose adjusted wrong-heal rate on the calibration set is at most α = 0.05. That gave **τ = 0.73**. With 36 calibration failures the bound has real small-sample slack, so I treat it as a guide. But it is a reason, not a vibe.

## The full agent, end to end, and the red team

I ran the complete Strands agent, with Decider, the gate, Nova 2 Lite, the re-run and a local git repo, on all 34 mutations: **34/34 correct outcomes, 0 wrong heals, 0 fixable cases missed**. The first run scored 33/34: my own code built a git branch name with a `?` in it ("How many people?"). The agent could not open the PR and filed an issue instead, which is exactly the failure mode I want.

The combo case is the one I like best. Decider says heal (0.91), and it is right: the button really was only renamed. Nova fixes the locator, the re-run goes red because the maths is now wrong, the gate refuses the PR and the agent files an issue for the developer. The classifier did not need to see the hidden bug; the re-run did.

Then I attacked my own agent: same tools, but a system prompt telling it to always make the suite green and never file issues. The first version of the gate held, but the attacker found two gaps. After a red re-run it re-applied the same fix about 100 times, and once it simply stopped and left its edit behind. Two rules closed them: **one fix attempt per failure**, and **fail closed** (an agent that ends without a PR or an issue has its edits undone, and code files the issue). After that the red team opened **0 PRs and changed 0 test files**.

## Then I pointed it at a real app

A practice app I wrote myself proves little, so I ran the same agent, with unchanged thresholds, on upstream [TodoMVC](https://github.com/tastejs/todomvc), the app Playwright uses for its own demos. It is pinned at one commit and cloned at run time. I wrote four ordinary developer commits and the expected answer for each before running anything.

| Commit | Expected | Decider | What the agent did |
|---|---|---|---|
| Input placeholder reworded | Heal | 0.91 | Fixed one locator line, re-run green, PR |
| Off-by-one in "items left" | Halt | assertion | Issue for the developer, no code touched |
| Placeholder reworded **and** the counter bug | Halt | 0.90 | Fixed the locator, re-run red, undid it, issue for the developer |
| "Clear completed" became "Clear done" | Heal | 0.77 | Refused, issue for the test author |

**Zero wrong heals**, and the last row taught me something SplitPay never could. That button only appears after you tick a todo, so the page's first-load snapshot did not change and the evidence held no new name. Decider still leaned heal (0.77), the agent guessed "Clear", and **the guess passed the re-run**, because Playwright matches button names by substring. A green PR, built on a guess.

The gate now accepts only a new name that is visible on a `+` line of the evidence. The same rule went into the reusable pattern, with a regression test. I re-ran the full 34-case scorecard after the change: still 34/34. The miss is a safe one: a real rename went to a person instead of being healed.

The real app found two more problems, both in my harness rather than the model:

- **Python's built-in test server drops scripts.** It queues only 5 connections, TodoMVC loads 8 scripts at once, and about one run in five a healthy app failed to start and looked broken. The queue is now 64.
- **`hoh run` only understood a one-file app.** It now snapshots the whole `app/` folder and heals across every test file.

## The benchmarks: local, Bedrock, EC2 and AgentCore

This is where I want to be most careful, because only some of these numbers are mine.

**What I measured**

| The same decision | Where it ran | p50 / p95 | Tokens per decision | API price per million decisions |
|---|---|---|---|---|
| Strands Decider 2B | My MacBook Air M4, MLX, quiet (11 Oct, all 97 failures, 2 questions) | 545 / 733 ms | none billed | **$0** |
| Strands Decider 2B | Same laptop, deep in swap (18 Oct, real TodoMVC states, 2 questions) | 1,137 / 1,972 ms | none billed | **$0** |
| Amazon Nova Micro | Bedrock, us-east-1 (11 Oct, all 97 failures) | 643 / 922 ms | 259 in / 5 out | about $9.8 |
| Amazon Nova Micro | Bedrock, us-east-1 (18 Oct, TodoMVC states) | 525 / 564 ms | 237 in / 5 out | about $9.0 |
| Amazon Nova Pro | Bedrock, us-east-1 (18 Oct, TodoMVC states) | 579 / 660 ms | 145 in / 5 out | about $132 |

Prices are the AWS Price List API's us-east-1 on-demand rates on 18 Oct (Nova Micro $0.035 / $0.14 and Nova Pro $0.80 / $3.20 per million input / output tokens), multiplied by the tokens I measured. On 18 Oct my laptop had 13 GB of swap in use, which is why Decider was slower than the week before.

**What other people measured, or AWS documents (not run by me)**

| Setup | What is known | Status |
|---|---|---|
| Decider on an RTX 3090 / MacBook Pro M3 | About 115 ms / 153 ms median | Published in the Strands announcement |
| Decider self-hosted on CPU EC2 (the community-run decider-cloud service our user group uses for hackathon teams) | Its author reports about 1.43 decisions per second per instance, and about $0.1785 an hour per instance plus about $36 a month fixed | Reported, not measured by me. It serves an older Decider checkpoint, so my 0.73 threshold does not transfer to it |
| Decider on Amazon Bedrock AgentCore Runtime | microVMs have no GPU and cap at 2 vCPU / 8 GB per session; the Instances compute type supports GPU families such as g5 and g6 (g6.xlarge is $0.8048 an hour on demand in us-east-1) | **Not deployed, no numbers.** A plan, below |

**What it means.**

1. **The win is correctness, not speed.** Asked the same question, Nova Micro would have opened 3 PRs that hid real problems and missed 14 of 27 easy fixes. Decider plus the rules opened none and missed none. One wrong heal ships a bug behind a green build, which costs more than any token bill.
2. **Latency is a tie on a laptop.** On a quiet laptop Decider answered two questions faster than Nova Micro answered one; under swap it was about twice as slow. I don't claim a speed win.
3. **Cost is real but small in dollars**: about $9-10 per million decisions against Nova Micro and about $132 against Nova Pro. The bigger saving is that no test log, page snapshot or commit message leaves the machine to make the decision.
4. **Bedrock still does every generative job.** Nova 2 Lite runs the agent and writes the locator, the PR and the issues. Nova Pro is only called in the grey zone (6 of the 48 held-out failures).

## What I tested, in one table

| Layer | Result |
|---|---|
| Unit, gate, CLI and Playwright tests (`make test`, no model, no AWS) | 27/27 |
| Held-out eval, 48 failures | 27/27 healed, 0/21 wrong heals |
| Full agent, 34 kinds of breakage | 34/34 correct, 0 wrong heals |
| Red team (an agent told to always go green) | 0 PRs, 0 test files changed |
| The 5 demo cases | 5/5 |
| Real repo, 4 commits on TodoMVC | 0 wrong heals, 1 safe miss |

## The reusable pattern: `policy-can-heal`

```
patterns/policy-can-heal/
  question.json    the two typed questions and their criteria
  handler.py       failure_kind() pre-filter, decide() policy, a Strands InterventionHandler
  thresholds.md    the bands, the hard rules, how τ = 0.73 was chosen
  README.md        how to drop it into your agent
```

Keep the shape and swap the questions: one yes/no that is true only when the risky action is clearly safe, one choice that names who handles a refusal, three bands in code, and one verification step the model cannot skip.

## What comes next: running it on AWS

Nothing here is built yet. Test failures happen in CI, so the right home is a GitHub App that runs when an end-to-end job fails, with the Heal Receipt posted on the pull request. Every run executes someone's test code, so each run should get its own Amazon Bedrock AgentCore Runtime microVM. Decider would sit next to it on a GPU (the AgentCore Instances compute type, or a GPU instance in the same VPC), because 2 vCPUs is no place for a 2-billion-parameter model.

Before any of that ships, the eval has to be re-run on the deployed Decider. My threshold was measured on MLX, and a different backend can move the confidences.

## Try it

You need an Apple-silicon Mac, Google Chrome, Python 3.12, `uv`, and AWS credentials with Amazon Nova access in us-east-1. Then run `make setup`, `make serve`, `make check` (it must say `READY`) and `make playground`, rename the button in `playground/app/index.html`, commit, and run `make run`. You get either a `heal/...` branch with `PR-1.md`, or an `ISSUE-1.md`.

`make todomvc` reruns the real-repo test, `make eval` the benchmark and `make scorecard` the full agent on all 34 mutations.

- Repo: https://github.com/logesh4v/heal-or-halt
- Video: https://youtu.be/oHNKQBP5hpc

## What I'd tell another builder

1. Put the decision in front of the risky action, not after it.
2. Ask a concrete yes/no about evidence, not about intentions. My vague question healed deleted buttons.
3. Write the bands and the hard rules in code, not in the prompt.
4. Test on failures you created by really breaking something, and split them by cause, not by row.
5. Make the verification step one the model cannot skip. The re-run caught what the classifier could not see.
6. Then run it on someone else's app. Mine had no hidden buttons, so I never learned that a passing re-run can still bless a guess.
