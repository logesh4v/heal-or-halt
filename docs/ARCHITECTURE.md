# Heal or Halt: architecture

**Bedrock writes, Decider decides, code verifies.**

## 1. The whole system

```mermaid
flowchart TB
  classDef det fill:#e0e7ff,stroke:#4f46e5,color:#1e1b4b
  classDef dec fill:#fef3c7,stroke:#d97706,color:#78350f
  classDef llm fill:#dcfce7,stroke:#16a34a,color:#14532d
  classDef stop fill:#fee2e2,stroke:#dc2626,color:#7f1d1d

  T["Playwright suite<br/>(SplitPay)"]:::det --> C["Collector<br/>step · locator · error ·<br/>aria diff · commit"]:::det
  C --> F{"failure_kind<br/>(code)"}:::det
  F -->|assertion| H1["HALT → developer"]:::stop
  F -->|page did not load| H2["HALT → platform"]:::stop
  F -->|locator| D["Decider 2B, 127.0.0.1<br/>can_heal + halt_reason"]:::dec
  D -->|"≥ 0.73"| A["Strands agent<br/>Nova 2 Lite"]:::llm
  D -->|"0.55–0.73"| V["Nova Pro<br/>veto only"]:::llm
  D -->|"< 0.55"| H3["HALT → owner"]:::stop
  V -->|UNSAFE| H3
  V -->|SAFE| HU["human approves"]
  A -->|apply_locator_fix| G{"HealGate<br/>(code)"}:::det
  G -->|"PROCEED"| R["re-run suite"]:::det
  R -->|green| P["open_pr → PR + receipt"]
  R -->|red| H4["file_issue → developer"]:::stop
  G -->|"DENY ×3"| L["lockout → issue by code"]:::stop
```

Blue = deterministic code. Amber = the decision (local). Green = Amazon Bedrock. Red = halt.

## 2. One heal, start to end (measured: btn-rename-0)

```mermaid
sequenceDiagram
  participant S as Suite + collector
  participant D as Decider 2B
  participant A as Agent (Nova 2 Lite)
  participant G as HealGate
  S->>D: 3 failures, one root cause: get_by_role("button", name="Split bill")
  D-->>A: can_heal 0.92 -> HEAL, owner test_author
  A->>G: apply_locator_fix("Split bill", "Calculate shares")
  G-->>A: PROCEED (right locator, new name differs)
  A->>S: rerun_tests
  S-->>A: GREEN
  A->>G: open_pr
  G-->>A: PROCEED (verdict HEAL, re-run green)
  A-->>S: branch heal/split-bill-to-calculate-shares + PR-1.md receipt
```

The combo case follows the same path until the re-run: it comes back RED (the maths is wrong too), the gate refuses `open_pr`, and the agent files an issue for the developer.

## 3. The rules (patterns/policy-can-heal/handler.py, hoh/agent.py)

| Check, in order | Result |
|---|---|
| Assertion failure | HALT, developer. Assertions are never healed |
| Page did not load | HALT, platform |
| can_heal < 0.55 | HALT, `halt_reason`'s owner (test_author when the page did not change at all) |
| New locator still contains the old name | DENY |
| Fix targets a locator other than the failing one | DENY |
| 0.55 ≤ can_heal < 0.73 | Nova Pro second opinion; UNSAFE → HALT, SAFE → human |
| can_heal ≥ 0.73 | the agent may fix |
| Re-run not green | `open_pr` DENIED |
| 3 healed locators in one commit | DENY, likely redesign (blast radius) |
| 3 denied attempts in one case | lockout, case halted by code |

## 4. Security

- The Decider server has no auth: bound to 127.0.0.1 only. The demo app server too.
- AWS: boto3 reads the named profile; no keys in code (scanned).
- The agent's "PRs" and "issues" are local git branches and markdown files under `demo-run/`; nothing is pushed.
- The receipt's facts (decision, diff, re-run result, commit) are inserted by code; the model writes only the prose.
