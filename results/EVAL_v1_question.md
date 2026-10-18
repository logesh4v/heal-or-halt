# Heal or Halt eval

97 real failures from 34 mutations. Held-out split by mutation: 16 calibration / 17 test mutations (48 test cases).

Conformal threshold for alpha=0.1: tau=0.75

| Test split | Healable healed | Wrong heals | Accuracy |
|---|---|---|---|
| decider_policy_tau | 22/27 | 4/21 | 0.812 |
| decider_policy_0.70 | 27/27 | 5/21 | 0.896 |
| decider_raw_0.50 | 27/27 | 15/21 | 0.688 |
| rule_baseline | 24/27 | 3/21 | 0.875 |
| nova_micro | 3/27 | 4/21 | 0.417 |

Gray zone (sent to a human) on the test split: 15
Halt owner routing accuracy (all non-heal cases): 0.65
Latency: {'decider_p50': 463, 'decider_p95': 611, 'nova_micro_p50': 651, 'nova_micro_p95': 852}
p(can_heal) range by truth: {'combo': [0.74, 0.75], 'developer': [0.36, 0.79], 'heal': [0.69, 0.86], 'platform': [0.34, 0.6], 'test_author': [0.47, 0.71]}
Combo cases (must be caught by the re-run gate): [{'mutation': 'combo-rename-math', 'step': 'test_even_split', 'p': 0.747}, {'mutation': 'combo-rename-math', 'step': 'test_rounds_to_paise', 'p': 0.753}, {'mutation': 'combo-rename-math', 'step': 'test_zero_people_shows_error', 'p': 0.744}]
Nova Micro tokens: {'input': 21945, 'output': 485, 'unparsed': 0}
