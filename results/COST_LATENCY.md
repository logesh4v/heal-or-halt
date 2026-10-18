# Cost and latency: Decider 2B (local) vs asking a Bedrock model

The decision in question: "is it safe to heal this failing test?" Everything else (writing the PR, the
issue, the agent loop) runs on Amazon Nova either way, so only this one decision is compared.

## The table

| | Strands Decider 2B, local | Amazon Nova Micro | Amazon Nova Pro |
|---|---|---|---|
| **Wrong heals, held-out eval (lower is better)** | **0/21** with the rules (0.77 accuracy, 11/21 wrong, without them) | 3/21 | not measured (used only as a veto) |
| **Fixable failures healed** | **27/27** | 13/27 | not measured |
| **Accuracy, held-out 48 failures** | **1.00** | 0.65 | not measured |
| Latency p50 / p95, quiet laptop (11 Oct) | 545 / 733 ms, 2 questions | 643 / 922 ms, 1 question | - |
| Latency p50 / p95, real TodoMVC states (18 Oct) | 1,137 / 1,972 ms, 2 questions | 525 / 564 ms | 579 / 660 ms |
| Tokens per decision | none billed | 237 in / 5 out (TodoMVC); ~524 in / ~10 out (eval) | 145 in / 5 out |
| **Price per 1 million decisions** | **$0 API cost** (runs on a machine you already have; ~4 GB peak memory) | ~$9 (TodoMVC) to ~$20 (eval prompt) | ~$132 |
| Failure data leaves the machine? | **No** | Yes, to Bedrock | Yes, to Bedrock |

## What it means, honestly

1. **The win is correctness, not speed.** On the held-out eval, asking Nova Micro the same question
   would have opened 3 PRs that hid real bugs and missed 14 of 27 easy fixes. Decider plus the rules
   opened none and missed none. One wrong heal ships a bug behind a green build, which costs far more
   than any token bill. Decider alone (no rules) makes 11 wrong heals: **the model and the rules together
   are the product**, not either one alone.
2. **Latency is a tie at best on a laptop.** On a quiet machine Decider answered two questions in less time
   than Nova Micro took for one. On 18 Oct the same laptop had 13 GB of swap in use, and Decider was about
   2x slower than Nova Micro. For a test failure, either is fast enough; we do not claim a latency win.
3. **Cost is real but small in dollars.** Moving the decision off Bedrock saves about $9-20 per million
   decisions against Nova Micro and about $132 against Nova Pro. The bigger saving is that no test log,
   page snapshot or commit message is sent anywhere to make the decision.
4. **Where the money actually goes:** Nova Pro is only called in the grey zone (6 of 48 held-out cases),
   and Nova 2 Lite writes PRs and issues. Those calls stay, because writing text is Bedrock's job.

## Sources

| Number | Where it comes from |
|---|---|
| Accuracy, wrong heals, healed counts | `results/eval.json` -> `summary.test_split` (held-out: 17 mutation kinds, 48 failures; 11 Oct) |
| 11 Oct latency, Nova Micro eval tokens (25,146 in / 485 out over 48 calls) | `results/EVAL.md` |
| 18 Oct latency and tokens on TodoMVC | `results/bench_todomvc.json`, from `examples/todomvc/bench.py` (4 real failure states x 5 reps, warm, us-east-1) |
| Decider peak memory (3.75-4.3 GiB for short states) | `results/bench_mlx.csv` |
| Swap in use on 18 Oct | `sysctl vm.swapusage`: 13,084 MB of 14,336 MB used during the bench |
| Prices | AWS Price List API, `AmazonBedrock`, us-east-1, on-demand, queried 18 Oct 2026: Nova Micro $0.035 / $0.14 and Nova Pro $0.80 / $3.20 per million input / output tokens |
| Price per million decisions | tokens per decision x those prices (Micro: 237 x 0.035 + 5 x 0.14 = $9.0; Pro: 145 x 0.80 + 5 x 3.20 = $132) |
