"""
The optimization model.

Question: how many kg should each carrier take on each lane, so that the freight bill is as low as possible
while service (on-time delivery) and business limits are respected?

Decision variable    x[lane, carrier]  = kg given to that carrier on that lane (one per existing offer)
Minimize             sum( price_per_kg x kg )
Subject to
  1. every lane's demand is fully shipped                    sum over carriers of x = demand(lane)
  2. no carrier exceeds its monthly capacity                 sum over lanes of x <= capacity(carrier)
  3. share limits per carrier (commitments / concentration)  min_share x total <= sum over lanes <= max_share x total
  4. overall on-time rate >= target                          sum(on_time x kg) >= target x total
  5. on-time floor in every region (no region sacrificed)    sum(on_time x kg) >= floor x demand(region)
  6. optional: no carrier takes more than X% of a lane       kg <= X x demand(lane)
  7. optional: minimum lot (a carrier either takes at least N kg on a lane or nothing)  -> needs integer variables

Without constraint 7 the problem is a linear program (LP) solved with HiGHS. With 7 it becomes a mixed-integer
program (MILP). Only the LP has "shadow prices", the price of tightening a constraint by one unit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

TOL = 1e-6


@dataclass
class Problem:
    lanes: pd.DataFrame      # lane, region, demand_kg
    carriers: pd.DataFrame   # carrier, capacity_kg, min_share, max_share
    offers: pd.DataFrame     # lane, carrier, price_per_kg, on_time

    @property
    def total_kg(self) -> float:
        return float(self.lanes["demand_kg"].sum())

    def with_price_change(self, carrier: str, pct: float) -> "Problem":
        offers = self.offers.copy()
        offers.loc[offers["carrier"] == carrier, "price_per_kg"] *= 1 + pct
        return Problem(self.lanes, self.carriers, offers)


@dataclass(frozen=True)
class Rules:
    ontime_target: float = 0.0
    region_floor: float = 0.0
    lane_max_share: float = 1.0
    min_lot_kg: float = 0.0


@dataclass
class Solution:
    feasible: bool
    message: str
    allocation: pd.DataFrame = field(default_factory=pd.DataFrame)   # lane, carrier, kg, price_per_kg, on_time
    cost: float = float("nan")
    ontime: float = float("nan")
    cost_per_extra_pp: float | None = None    # shadow price of the on-time constraint, R$ per +1 percentage point


def load_problem(data_dir) -> Problem:
    d = Path(data_dir)
    return Problem(pd.read_csv(d / "lanes.csv"), pd.read_csv(d / "carriers.csv"), pd.read_csv(d / "offers.csv"))


def evaluate(problem: Problem, allocation: pd.DataFrame) -> tuple[float, float]:
    """(cost in R$, overall on-time rate) of any allocation, optimized or not."""
    m = allocation[["lane", "carrier", "kg"]].merge(problem.offers, on=["lane", "carrier"], how="left")
    if m["price_per_kg"].isna().any():
        raise ValueError("allocation uses a carrier that does not serve that lane")
    kg = m["kg"].to_numpy()
    return float((kg * m["price_per_kg"]).sum()), float((kg * m["on_time"]).sum() / kg.sum())


# ----------------------------------------------------------------------------
# Building the matrices
# ----------------------------------------------------------------------------
class _Model:
    def __init__(self, problem: Problem, rules: Rules):
        o = problem.offers.reset_index(drop=True)
        lanes = problem.lanes.set_index("lane")
        car = problem.carriers.set_index("carrier")
        self.offers, self.n, self.total = o, len(o), problem.total_kg
        price, ot = o["price_per_kg"].to_numpy(), o["on_time"].to_numpy()
        self.price = price

        def row(mask):
            return mask.astype(float)

        eq_rows, eq_rhs = [], []
        for lane, d in lanes["demand_kg"].items():
            eq_rows.append(row((o["lane"] == lane).to_numpy())); eq_rhs.append(d)

        ub_rows, ub_rhs = [], []
        for c, r in car.iterrows():
            mask = (o["carrier"] == c).to_numpy()
            ub_rows.append(row(mask)); ub_rhs.append(r["capacity_kg"])
            ub_rows.append(row(mask)); ub_rhs.append(r["max_share"] * self.total)
            if r["min_share"] > 0:
                ub_rows.append(-row(mask)); ub_rhs.append(-r["min_share"] * self.total)
        self.ontime_row = len(ub_rows)
        ub_rows.append(-ot); ub_rhs.append(-rules.ontime_target * self.total)
        if rules.region_floor > 0:
            for region, g in lanes.groupby("region"):
                mask = o["lane"].isin(g.index).to_numpy()
                ub_rows.append(-ot * mask); ub_rhs.append(-rules.region_floor * g["demand_kg"].sum())

        ub = np.full(self.n, np.inf)
        for i, r in o.iterrows():
            ub[i] = min(lanes.loc[r["lane"], "demand_kg"] * rules.lane_max_share, car.loc[r["carrier"], "capacity_kg"])
        self.ub = ub
        self.A_eq, self.b_eq = np.array(eq_rows), np.array(eq_rhs)
        self.A_ub, self.b_ub = np.array(ub_rows), np.array(ub_rhs)
        self.ot = ot


def _allocation(model: _Model, x: np.ndarray) -> pd.DataFrame:
    a = model.offers[["lane", "carrier", "price_per_kg", "on_time"]].copy()
    a["kg"] = np.where(x < 1e-6, 0.0, x).round(3)
    return a[a["kg"] > 0][["lane", "carrier", "kg", "price_per_kg", "on_time"]].reset_index(drop=True)


def solve(problem: Problem, rules: Rules = Rules()) -> Solution:
    m = _Model(problem, rules)
    if rules.min_lot_kg <= 0:
        res = linprog(m.price, A_ub=m.A_ub, b_ub=m.b_ub, A_eq=m.A_eq, b_eq=m.b_eq,
                      bounds=list(zip(np.zeros(m.n), m.ub)), method="highs")
        if res.status != 0:
            return Solution(False, "infeasible: the rules cannot all be met" if res.status == 2 else res.message)
        alloc = _allocation(m, res.x)
        cost, ontime = evaluate(problem, alloc)
        # marginals[row] = change in cost per +1 unit of that row's right-hand side (kg-points). The row is
        # -sum(ot x) <= -target x total, so +1 pp of target moves the right-hand side by -0.01 x total.
        shadow = float(-res.ineqlin.marginals[m.ontime_row] * 0.01 * m.total)
        return Solution(True, "optimal (linear program)", alloc, cost, ontime, shadow)

    # MILP: add one binary y per offer. y = 1 means "this carrier is used on this lane".
    n = m.n
    c = np.concatenate([m.price, np.zeros(n)])
    A_eq = np.hstack([m.A_eq, np.zeros((len(m.A_eq), n))])
    A_ub = np.hstack([m.A_ub, np.zeros((len(m.A_ub), n))])
    link_hi = np.hstack([np.eye(n), -np.diag(m.ub)])                 # x - ub*y <= 0
    link_lo = np.hstack([np.eye(n), -rules.min_lot_kg * np.eye(n)])  # x - lot*y >= 0
    cons = [LinearConstraint(A_eq, m.b_eq, m.b_eq),
            LinearConstraint(A_ub, -np.inf, m.b_ub),
            LinearConstraint(link_hi, -np.inf, 0),
            LinearConstraint(link_lo, 0, np.inf)]
    res = milp(c, constraints=cons, integrality=np.concatenate([np.zeros(n), np.ones(n)]),
               bounds=Bounds(np.zeros(2 * n), np.concatenate([m.ub, np.ones(n)])))
    if not res.success:
        return Solution(False, "infeasible: the rules cannot all be met" if res.status == 2 else str(res.message))
    alloc = _allocation(m, res.x[:n])
    cost, ontime = evaluate(problem, alloc)
    return Solution(True, "optimal (mixed-integer program)", alloc, cost, ontime, None)


def max_ontime(problem: Problem, rules: Rules = Rules()) -> float:
    """The highest overall on-time rate reachable under all the other rules (ignores rules.ontime_target)."""
    m = _Model(problem, Rules(0.0, rules.region_floor, rules.lane_max_share, 0.0))
    res = linprog(-m.ot, A_ub=m.A_ub, b_ub=m.b_ub, A_eq=m.A_eq, b_eq=m.b_eq,
                  bounds=list(zip(np.zeros(m.n), m.ub)), method="highs")
    if res.status != 0:
        raise ValueError("no allocation satisfies the capacity and share limits")
    return float(-res.fun / m.total)


# ----------------------------------------------------------------------------
# Independent checker (does not use the matrices above)
# ----------------------------------------------------------------------------
def check(problem: Problem, rules: Rules, allocation: pd.DataFrame) -> list[str]:
    """Returns a list of broken rules (empty list = the allocation is valid)."""
    bad = []
    a = allocation.merge(problem.offers, on=["lane", "carrier"], how="left", suffixes=("", "_o"))
    if a["price_per_kg"].isna().any():
        return ["uses a carrier on a lane it does not serve"]
    lanes = problem.lanes.set_index("lane")
    for lane, d in lanes["demand_kg"].items():
        got = a.loc[a["lane"] == lane, "kg"].sum()
        if abs(got - d) > 0.01:
            bad.append(f"demand of {lane}: {got:.1f} vs {d}")
    for r in problem.carriers.itertuples():
        kg = a.loc[a["carrier"] == r.carrier, "kg"].sum()
        if kg > r.capacity_kg + 0.01: bad.append(f"capacity of {r.carrier}")
        if kg > r.max_share * problem.total_kg + 0.01: bad.append(f"max share of {r.carrier}")
        if kg < r.min_share * problem.total_kg - 0.01: bad.append(f"min share of {r.carrier}")
    if (a["kg"] * a["on_time"]).sum() / a["kg"].sum() < rules.ontime_target - TOL: bad.append("overall on-time target")
    a["region"] = a["lane"].map(lanes["region"])
    for region, g in a.groupby("region"):
        if (g["kg"] * g["on_time"]).sum() / g["kg"].sum() < rules.region_floor - TOL: bad.append(f"on-time floor in {region}")
    share = a["kg"] / a["lane"].map(lanes["demand_kg"])
    if (share > rules.lane_max_share + TOL).any(): bad.append("lane concentration cap")
    if rules.min_lot_kg > 0 and ((a["kg"] > 0) & (a["kg"] < rules.min_lot_kg - 0.01)).any(): bad.append("minimum lot")
    return bad
