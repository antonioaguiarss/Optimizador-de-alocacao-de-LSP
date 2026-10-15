import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from allocator import Problem, Rules, check, evaluate, load_problem, max_ontime, solve  # noqa: E402
from allocator.synthetic import generate  # noqa: E402


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    generate(d)
    problem = load_problem(d)
    baseline = pd.read_csv(d / "baseline.csv")
    cost, ot = evaluate(problem, baseline)
    return problem, baseline, cost, ot


def test_tiny_problem_by_hand():
    """Two carriers, one lane, 100 kg. A is cheap (R$1) and 60% on time, B costs R$2 and is 100% on time.
    With target 80% on time we need 50 kg on each: cost = 50*1 + 50*2 = 150."""
    p = Problem(pd.DataFrame({"lane": ["L"], "region": ["R"], "demand_kg": [100.0]}),
                pd.DataFrame({"carrier": ["A", "B"], "capacity_kg": [100.0, 100.0], "min_share": [0.0, 0.0], "max_share": [1.0, 1.0]}),
                pd.DataFrame({"lane": ["L", "L"], "carrier": ["A", "B"], "price_per_kg": [1.0, 2.0], "on_time": [0.6, 1.0]}))
    s = solve(p, Rules(ontime_target=0.8))
    assert s.cost == pytest.approx(150.0)
    assert s.ontime == pytest.approx(0.8)
    # shadow price: +1 pp on-time = 2.5 kg moved from A to B, each costing R$1 more -> R$2.5
    assert s.cost_per_extra_pp == pytest.approx(2.5)


def test_current_plan_is_valid_under_default_rules(world):
    problem, baseline, _, ot = world
    assert check(problem, Rules(ot, 0.80), baseline) == []


def test_optimized_plan_is_valid_and_not_more_expensive(world):
    problem, baseline, cost, ot = world
    rules = Rules(ot, 0.80)
    s = solve(problem, rules)
    assert s.feasible and check(problem, rules, s.allocation) == []
    assert s.cost <= cost + 1e-6
    assert s.ontime >= ot - 1e-6


def test_shadow_price_matches_finite_difference(world):
    problem, _, _, ot = world
    base = solve(problem, Rules(ot, 0.80))
    bumped = solve(problem, Rules(ot + 0.0005, 0.80))   # +0.05 percentage point
    measured = (bumped.cost - base.cost) / 0.05
    assert measured == pytest.approx(base.cost_per_extra_pp, rel=0.02)


def test_cost_never_decreases_when_service_target_rises(world):
    problem, _, _, ot = world
    costs = [solve(problem, Rules(t, 0.80)).cost for t in (ot - 0.01, ot, ot + 0.01, ot + 0.02)]
    assert costs == sorted(costs)


def test_target_above_reachable_is_infeasible(world):
    problem, *_ = world
    top = max_ontime(problem, Rules(region_floor=0.80))
    s = solve(problem, Rules(top + 0.01, 0.80))
    assert not s.feasible and "infeasible" in s.message
    assert solve(problem, Rules(top - 1e-4, 0.80)).feasible


def test_lane_cap_is_respected_and_costs_something(world):
    problem, _, _, ot = world
    free = solve(problem, Rules(ot, 0.80))
    capped = solve(problem, Rules(ot, 0.80, lane_max_share=0.70))
    assert check(problem, Rules(ot, 0.80, lane_max_share=0.70), capped.allocation) == []
    assert capped.cost >= free.cost - 1e-6


def test_minimum_lot_milp(world):
    problem, _, _, ot = world
    rules = Rules(ot, 0.80, min_lot_kg=10_000)
    free = solve(problem, Rules(ot, 0.80))
    s = solve(problem, rules)
    assert s.feasible and "mixed-integer" in s.message
    assert s.allocation["kg"].min() >= 10_000 - 0.01
    assert check(problem, rules, s.allocation) == []
    assert s.cost >= free.cost - 1e-6


def test_checker_catches_a_bad_plan(world):
    problem, baseline, _, ot = world
    bad = baseline.copy()
    bad.loc[bad["carrier"] == "Norte Sul", "kg"] *= 3   # breaks demand and the share limit
    assert check(problem, Rules(ot, 0.80), bad)


def test_same_seed_same_data(tmp_path):
    generate(tmp_path / "a", seed=4); generate(tmp_path / "b", seed=4)
    for f in ("offers.csv", "baseline.csv"):
        assert (tmp_path / "a" / f).read_text() == (tmp_path / "b" / f).read_text()
