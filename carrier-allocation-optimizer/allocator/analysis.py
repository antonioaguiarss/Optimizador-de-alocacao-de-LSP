"""Questions a manager asks after seeing the first answer."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .model import Problem, Rules, evaluate, max_ontime, solve


def pareto(problem: Problem, rules: Rules, low: float, steps: int = 25) -> pd.DataFrame:
    """Cheapest plan for each on-time target, from `low` up to the highest reachable rate."""
    top = max_ontime(problem, rules)
    rows = []
    for t in np.linspace(low, top - 1e-4, steps):
        s = solve(problem, Rules(float(t), rules.region_floor, rules.lane_max_share, rules.min_lot_kg))
        if s.feasible:
            rows.append({"ontime_target": round(float(t), 4), "cost": round(s.cost, 2),
                         "cost_per_extra_pp": round(s.cost_per_extra_pp, 2) if s.cost_per_extra_pp is not None else None})
    return pd.DataFrame(rows)


def price_shock(problem: Problem, rules: Rules, current_plan: pd.DataFrame, pct: float = 0.08) -> pd.DataFrame:
    """For each carrier: what if its prices rise by `pct`? Compare keeping the current plan vs re-optimizing."""
    rows = []
    for c in problem.carriers["carrier"]:
        shocked = problem.with_price_change(c, pct)
        keep, _ = evaluate(shocked, current_plan)
        new = solve(shocked, rules)
        rows.append({"carrier": c, "cost_keeping_plan": round(keep, 2), "cost_reoptimized": round(new.cost, 2),
                     "saved_by_reoptimizing": round(keep - new.cost, 2),
                     "kg_share_after": round(new.allocation.loc[new.allocation["carrier"] == c, "kg"].sum() / problem.total_kg, 4)})
    return pd.DataFrame(rows)


def cost_of_rules(problem: Problem, rules: Rules, concentration_cap: float = 0.70, min_lot_kg: float = 10_000) -> pd.DataFrame:
    """How much does each business rule cost? Re-solve with the rule on and compare with the plan without it."""
    base = solve(problem, Rules(rules.ontime_target, rules.region_floor))
    out = [{"scenario": "Plan with the base rules", "cost": base.cost, "ontime": base.ontime}]
    capped = solve(problem, Rules(rules.ontime_target, rules.region_floor, lane_max_share=concentration_cap))
    out.append({"scenario": f"+ no carrier above {concentration_cap:.0%} of a lane", "cost": capped.cost, "ontime": capped.ontime})
    lot = solve(problem, Rules(rules.ontime_target, rules.region_floor, min_lot_kg=min_lot_kg))
    out.append({"scenario": f"+ minimum lot of {min_lot_kg:,.0f} kg per carrier/lane", "cost": lot.cost, "ontime": lot.ontime})
    out = pd.DataFrame(out)
    out["extra_cost_vs_base"] = (out["cost"] - base.cost).round(2)
    out["cost"] = out["cost"].round(2)
    out["ontime"] = out["ontime"].round(4)
    return out


def by_carrier(problem: Problem, allocation: pd.DataFrame) -> pd.DataFrame:
    a = allocation[["lane", "carrier", "kg"]].merge(problem.offers, on=["lane", "carrier"])
    g = a.assign(cost=a["kg"] * a["price_per_kg"], ot=a["kg"] * a["on_time"])
    g = g.groupby("carrier").agg(kg=("kg", "sum"), cost=("cost", "sum"), ot=("ot", "sum"))
    g = g.reindex(problem.carriers["carrier"]).fillna(0)
    g["share"] = g["kg"] / problem.total_kg
    g["avg_price_per_kg"] = np.where(g["kg"] > 0, g["cost"] / g["kg"].replace(0, np.nan), 0)
    g["on_time"] = np.where(g["kg"] > 0, g["ot"] / g["kg"].replace(0, np.nan), 0)
    return g.drop(columns="ot").reset_index()
