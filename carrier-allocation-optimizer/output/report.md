# Carrier allocation: results

Monthly volume: 725,000 kg on 8 lanes, 5 carriers.
Rules: every region at least 80% on time; carrier capacity and share limits from carriers.csv.

| | Cost / month | On-time |
|---|---|---|
| Current plan | R$ 979,803 | 86.6% |
| A. Same service, optimized | R$ 919,816 (-6.1%) | 86.6% |
| B. Same budget, best service | R$ 979,803 (-0.0%) | 90.1% |
| Highest on-time reachable | | 90.2% |

Shadow price at today's service level: **R$ 6,469** per extra percentage point of on-time.

## Price shock: +8% on one carrier (starting from plan A)

| carrier   |   cost_keeping_plan |   cost_reoptimized |   saved_by_reoptimizing |   kg_share_after |
|:----------|--------------------:|-------------------:|------------------------:|-----------------:|
| Norte Sul |              929127 |             926872 |                 2254.74 |           0.0845 |
| RodoFacil |              946396 |             933921 |                12475.1  |           0.18   |
| Atlantico |              950682 |             947018 |                 3663.97 |           0.2433 |
| Veloz     |              926645 |             924809 |                 1836.39 |           0.1785 |
| Mercurio  |              919816 |             919816 |                    0    |           0      |

## What each business rule costs

| scenario                                    |   cost |   ontime |   extra_cost_vs_base |
|:--------------------------------------------|-------:|---------:|---------------------:|
| Plan with the base rules                    | 919816 |   0.8655 |                 0    |
| + no carrier above 70% of a lane            | 928415 |   0.8655 |              8598.2  |
| + minimum lot of 10,000 kg per carrier/lane | 922526 |   0.8655 |              2709.46 |
