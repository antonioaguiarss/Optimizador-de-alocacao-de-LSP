"""
Runs the whole analysis and writes everything to output/.

    python scripts/run_optimization.py
    python scripts/run_optimization.py --region-floor 0.78 --lane-cap 0.7
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from allocator import Rules, check, evaluate, load_problem, max_ontime, solve  # noqa: E402
from allocator.analysis import by_carrier, cost_of_rules, pareto, price_shock  # noqa: E402
from allocator.charts import pareto_chart, shares_chart  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--data", default=str(ROOT / "data"))
ap.add_argument("--out", default=str(ROOT / "output"))
ap.add_argument("--region-floor", type=float, default=0.80, help="minimum on-time rate in every region")
ap.add_argument("--lane-cap", type=float, default=0.70, help="used in the 'cost of rules' scenario")
ap.add_argument("--min-lot", type=float, default=10000, help="used in the 'cost of rules' scenario (kg)")
args = ap.parse_args()
out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

problem = load_problem(args.data)
baseline = pd.read_csv(Path(args.data) / "baseline.csv")
b_cost, b_ot = evaluate(problem, baseline)
brl = lambda v: f"R$ {v:,.0f}"

# Scenario A: keep the service level you have today, pay less
rules_a = Rules(ontime_target=b_ot, region_floor=args.region_floor)
assert not check(problem, rules_a, baseline), "the current plan breaks the rules: lower the region floor"
a = solve(problem, rules_a)
# Scenario B: spend what you spend today, get the best service
top = max_ontime(problem, Rules(region_floor=args.region_floor))
lo, hi = b_ot, top
for _ in range(40):                      # bisection: highest target whose cheapest plan costs <= today
    mid = (lo + hi) / 2
    s = solve(problem, Rules(mid, args.region_floor))
    if s.feasible and s.cost <= b_cost: lo = mid
    else: hi = mid
b = solve(problem, Rules(lo, args.region_floor))

frontier = pareto(problem, Rules(0, args.region_floor), low=b_ot - 0.01)
shock = price_shock(problem, rules_a, a.allocation)
rules_cost = cost_of_rules(problem, rules_a, args.lane_cap, args.min_lot)

before, after = by_carrier(problem, baseline), by_carrier(problem, a.allocation)
a.allocation.to_csv(out / "optimized_allocation.csv", index=False)
b.allocation.to_csv(out / "optimized_same_budget_allocation.csv", index=False)
frontier.to_csv(out / "pareto_frontier.csv", index=False)
shock.to_csv(out / "price_shock.csv", index=False)
rules_cost.to_csv(out / "cost_of_rules.csv", index=False)
pareto_chart(frontier, b_cost, b_ot, out / "pareto.png")
shares_chart(before, after, out / "shares.png")

lines = ["# Carrier allocation: results", "",
         f"Monthly volume: {problem.total_kg:,.0f} kg on {len(problem.lanes)} lanes, {len(problem.carriers)} carriers.",
         f"Rules: every region at least {args.region_floor:.0%} on time; carrier capacity and share limits from carriers.csv.", "",
         "| | Cost / month | On-time |", "|---|---|---|",
         f"| Current plan | {brl(b_cost)} | {b_ot:.1%} |",
         f"| A. Same service, optimized | {brl(a.cost)} ({(a.cost - b_cost) / b_cost:+.1%}) | {a.ontime:.1%} |",
         f"| B. Same budget, best service | {brl(b.cost)} ({(b.cost - b_cost) / b_cost:+.1%}) | {b.ontime:.1%} |",
         f"| Highest on-time reachable | | {top:.1%} |", "",
         f"Shadow price at today's service level: **{brl(a.cost_per_extra_pp)}** per extra percentage point of on-time.", "",
         "## Price shock: +8% on one carrier (starting from plan A)", "", shock.to_markdown(index=False), "",
         "## What each business rule costs", "", rules_cost.to_markdown(index=False), ""]
(out / "report.md").write_text("\n".join(lines), encoding="utf-8")

print("\n".join(lines))
