# Carrier Allocation Optimizer

Decides **how many kg each carrier should carry on each lane** so the monthly freight bill is as low as possible, without hurting on-time delivery and respecting business limits (capacity, commitments, concentration).
It uses linear programming (SciPy / HiGHS) and mixed-integer programming for "minimum lot" rules.

> All data is **fictional**: 8 lanes from Campinas, 5 carriers, 725,000 kg per month.

🇧🇷 Versão em português: [README.pt-BR.md](README.pt-BR.md)

## The question, in plain words

Today the volume is split by habit. If I treat the split as a decision, what is the cheapest way to ship the same cargo with the same (or better) service? And what does each extra point of on-time delivery cost me?

## Results on the fictional data

| | Cost / month | On-time |
|---|---|---|
| Current plan | R$ 979,803 | 86.6% |
| **A.** Same service, optimized | **R$ 919,816 (-6.1%)** | 86.6% |
| **B.** Same budget, best service | R$ 979,803 | **90.1%** |
| Highest on-time reachable | | 90.2% |

- **A** saves about R$ 60 thousand per month (R$ 720 thousand per year) keeping today's service level.
- **B** spends exactly what is spent today and buys +3.5 percentage points of on-time.
- **Shadow price:** at today's service level, each extra percentage point costs about **R$ 6,469 per month**. Near the ceiling it explodes: the last 0.2 point costs about R$ 45 thousand (see the chart).

![Cost vs service](output/pareto.png)
![Shares](output/shares.png)

### What-if analyses (all in `output/report.md`)

- **Price shock (+8% on one carrier):** if RodoFacil raises prices 8%, keeping the plan costs R$ 12,475 more per month than re-optimizing. A carrier the plan does not use (Mercurio) changes nothing.
- **Cost of business rules:** forbidding any carrier from taking more than 70% of a lane costs +R$ 8,598/month (+0.9%). A minimum lot of 10,000 kg per carrier/lane costs +R$ 2,709/month (+0.3%). Rules have a price, and now it is visible.

## The model

- **Variables:** `x[lane, carrier]` = kg (only for lanes the carrier serves).
- **Minimize:** sum of price per kg × kg.
- **Constraints:** each lane's demand is fully shipped; carrier capacity; min/max share per carrier; overall on-time ≥ target; on-time ≥ 80% in every region; optional cap per lane; optional minimum lot (binary variables).
- Details in the docstring of `allocator/model.py`.

## Why you can trust the numbers

- `check()` is an **independent validator** that re-computes every constraint from the plain table, without the optimizer's matrices. Tests run it on every plan.
- The shadow price is **verified by finite difference** in a test (re-solve with +0.05 point of on-time and compare).
- A hand-solved two-carrier example (answer R$ 150, shadow price R$ 2.5) is a test.
- Impossible requests return "infeasible" instead of a wrong plan.

## How to run

```bash
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/run_optimization.py        # writes output/ (plans, pareto_frontier.csv, price_shock.csv, cost_of_rules.csv, charts, report.md)
pytest                                    # 10 tests
```

Options: `--region-floor 0.78 --lane-cap 0.7 --min-lot 10000`.
To use your own data, replace the CSVs in `data/` (`lanes`, `carriers`, `offers`, `baseline`) keeping the column names.

## Limits (read before using on real data)

- **On-time rate per carrier and lane is treated as fixed.** In real life, giving a carrier more volume can lower its performance. The model does not know that.
- One month, static; prices are linear in kg (no volume tiers).
- Capacity and share limits are inputs you must trust.
- The 100% reproducible numbers above come from fictional data built for this demo.
