# Agent scorecard (full Strands agent, every mutation)

Correct outcome: **34/34**. Wrong heals (PR on a non-healable): **0**. Healable cases not healed: **0**.

| Mutation | Truth | Outcome | Decision | OK |
|---|---|---|---|---|
| btn-rename-0 | heal | pr | `can_heal 0.92 -> HEAL (>= 0.73)` | yes |
| btn-rename-1 | heal | pr | `can_heal 0.95 -> HEAL (>= 0.73)` | yes |
| btn-rename-2 | heal | pr | `can_heal 0.92 -> HEAL (>= 0.73)` | yes |
| btn-rename-3 | heal | pr | `can_heal 0.89 -> HEAL (>= 0.73)` | yes |
| btn-rename-4 | heal | pr | `can_heal 0.89 -> HEAL (>= 0.73)` | yes |
| btn-rename-5 | heal | pr | `can_heal 0.88 -> HEAL (>= 0.73)` | yes |
| btn-rename-6 | heal | pr | `can_heal 0.76 -> HEAL (>= 0.73)` | yes |
| btn-rename-7 | heal | pr | `can_heal 0.93 -> HEAL (>= 0.73)` | yes |
| total-label-0 | heal | pr | `can_heal 0.94 -> HEAL (>= 0.73)` | yes |
| total-label-1 | heal | pr | `can_heal 0.92 -> HEAL (>= 0.73)` | yes |
| total-label-2 | heal | pr | `can_heal 0.93 -> HEAL (>= 0.73)` | yes |
| people-label-0 | heal | pr | `can_heal 0.94 -> HEAL (>= 0.73)` | yes |
| people-label-1 | heal | pr | `can_heal 0.94 -> HEAL (>= 0.73)` | yes |
| people-label-2 | heal | pr | `can_heal 0.93 -> HEAL (>= 0.73)` | yes |
| btn-to-input | heal | pr | `can_heal 0.91 -> HEAL (>= 0.73)` | yes |
| btn-aria-label | heal | pr | `can_heal 0.94 -> HEAL (>= 0.73)` | yes |
| btn-move-top | heal | pr | `can_heal 0.87 -> HEAL (>= 0.73)` | yes |
| btn-move-wrap | heal | pr | `can_heal 0.86 -> HEAL (>= 0.73)` | yes |
| math-multiply | developer | issue | `can_heal 0.53 -> HALT (assertion failed: assertions are never healed)` | yes |
| math-floor | developer | issue | `can_heal 0.55 -> HALT (assertion failed: assertions are never healed)` | yes |
| js-crash | developer | issue, issue | `can_heal 0.57 -> HALT (assertion failed: assertions are never healed)` | yes |
| btn-disabled | developer | issue | `can_heal 0.56 -> HALT (gray zone and Nova Pro vetoed the heal)` | yes |
| btn-removed | developer | issue | `can_heal 0.63 -> HALT (gray zone and Nova Pro vetoed the heal)` | yes |
| btn-hidden | developer | issue | `can_heal 0.63 -> HALT (gray zone and Nova Pro vetoed the heal)` | yes |
| people-input-removed | developer | issue | `can_heal 0.71 -> HALT (gray zone and Nova Pro vetoed the heal)` | yes |
| submit-noop | developer | issue, issue | `can_heal 0.55 -> HALT (assertion failed: assertions are never healed)` | yes |
| server-down | platform | issue | `can_heal 0.15 -> HALT (page did not load: environment problem)` | yes |
| server-500 | platform | issue | `can_heal 0.24 -> HALT (below 0.55: route to developer)` | yes |
| server-slow | platform | issue | `can_heal 0.21 -> HALT (page did not load: environment problem)` | yes |
| test-typo-button | test_author | issue | `can_heal 0.57 -> HALT (gray zone and Nova Pro vetoed the heal)` | yes |
| test-typo-label | test_author | issue | `can_heal 0.57 -> HALT (gray zone and Nova Pro vetoed the heal)` | yes |
| test-wrong-role | test_author | issue | `can_heal 0.55 -> HALT (gray zone and Nova Pro vetoed the heal)` | yes |
| test-wrong-expect | test_author | issue | `can_heal 0.60 -> HALT (assertion failed: assertions are never healed)` | yes |
| combo-rename-math | combo | issue | `can_heal 0.91 -> HEAL (>= 0.73)` | yes |
