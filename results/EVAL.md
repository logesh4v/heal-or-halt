# Heal or Halt eval

97 real failures from 34 mutations. Held-out split by mutation: 16 calibration / 17 test mutations (48 test cases).

Conformal threshold for alpha=0.05: tau=0.73

| Test split | Healable healed | Wrong heals | Accuracy |
|---|---|---|---|
| decider_policy_tau | 27/27 | 0/21 | 1.0 |
| decider_policy_0.70 | 27/27 | 0/21 | 1.0 |
| decider_policy_shipped | 27/27 | 0/21 | 1.0 |
| decider_raw_0.50 | 27/27 | 11/21 | 0.771 |
| rule_baseline | 24/27 | 3/21 | 0.875 |
| nova_micro | 13/27 | 3/21 | 0.646 |

Gray zone (sent to a human) on the test split: 6
Halt owner routing accuracy (all non-heal cases): 0.8
Latency: {'decider_p50': 545, 'decider_p95': 733, 'nova_micro_p50': 643, 'nova_micro_p95': 922}
p(can_heal) range by truth: {'combo': [0.85, 0.92], 'developer': [0.32, 0.72], 'heal': [0.66, 0.95], 'platform': [0.14, 0.26], 'test_author': [0.32, 0.6]}
Combo cases (must be caught by the re-run gate): [{'mutation': 'combo-rename-math', 'step': 'test_even_split', 'p': 0.911}, {'mutation': 'combo-rename-math', 'step': 'test_rounds_to_paise', 'p': 0.925}, {'mutation': 'combo-rename-math', 'step': 'test_zero_people_shows_error', 'p': 0.854}]
Nova Micro tokens: {'input': 25146, 'output': 485, 'unparsed': 0}
