"""
Fictional monthly freight volumes from one origin (Campinas) to 8 destinations, offered by 5 fictional carriers.
Everything is invented. Prices follow the same shape as the other projects in this portfolio:
price per kg = (0.20 + 0.0016 x km) x carrier factor.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# lane: (region, km, monthly demand in kg)
LANES = {
    "Sao Paulo":      ("Southeast",  100, 220_000),
    "Rio de Janeiro": ("Southeast",  500, 140_000),
    "Belo Horizonte": ("Southeast",  590,  90_000),
    "Curitiba":       ("South",      410,  80_000),
    "Porto Alegre":   ("South",     1100,  60_000),
    "Goiania":        ("Midwest",    930,  45_000),
    "Salvador":       ("Northeast", 1960,  50_000),
    "Recife":         ("Northeast", 2700,  40_000),
}

# carrier: (price factor, base on-time rate, capacity kg/month, min share, max share, lanes served)
CARRIERS = {
    "Norte Sul":  (0.88, 0.70, 320_000, 0.00, 0.35, list(LANES)),
    "RodoFacil":  (0.97, 0.84, 250_000, 0.05, 0.40, ["Sao Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Porto Alegre", "Goiania"]),
    "Atlantico":  (1.00, 0.86, 280_000, 0.05, 0.40, list(LANES)),
    "Veloz":      (1.18, 0.95, 200_000, 0.10, 0.40, list(LANES)),
    "Mercurio":   (1.60, 0.97,  60_000, 0.00, 0.08, ["Rio de Janeiro", "Belo Horizonte", "Porto Alegre", "Goiania", "Salvador", "Recife"]),
}
REGION_ONTIME_SHIFT = {"Southeast": 0.02, "South": 0.0, "Midwest": -0.02, "Northeast": -0.06}


def _baseline_shares(lane_names, carriers, rng):
    """Last quarter's actual split: habit-driven, leaning on Atlantico, Veloz and RodoFacil."""
    weights = {"Norte Sul": 0.12, "RodoFacil": 0.26, "Atlantico": 0.34, "Veloz": 0.24, "Mercurio": 0.04}
    rows = []
    for lane in lane_names:
        served = [c for c, v in carriers.items() if lane in v[5]]
        w = np.array([weights[c] * rng.uniform(0.75, 1.25) for c in served])
        w = w / w.sum()
        rows += [(lane, c, s) for c, s in zip(served, w)]
    return rows


def generate(out_dir, seed: int = 21) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    lanes = pd.DataFrame([{"lane": k, "region": v[0], "km": v[1], "demand_kg": v[2]} for k, v in LANES.items()])
    carriers = pd.DataFrame([{"carrier": k, "capacity_kg": v[2], "min_share": v[3], "max_share": v[4]}
                             for k, v in CARRIERS.items()])

    offers = []
    for c, (factor, base_ot, _cap, _mn, _mx, served) in CARRIERS.items():
        for lane in served:
            region, km, _d = LANES[lane]
            price = (0.20 + 0.0016 * km) * factor * rng.uniform(0.97, 1.03)
            ot = base_ot + REGION_ONTIME_SHIFT[region] + rng.normal(0, 0.012)
            offers.append({"lane": lane, "carrier": c, "price_per_kg": round(price, 4), "on_time": round(float(np.clip(ot, 0.5, 0.995)), 4)})
    offers = pd.DataFrame(offers)

    demand = lanes.set_index("lane")["demand_kg"]
    base = pd.DataFrame(_baseline_shares(list(LANES), CARRIERS, rng), columns=["lane", "carrier", "share"])
    base["kg"] = (base["share"] * base["lane"].map(demand)).round(0)
    # fix rounding so each lane still adds up to its demand exactly
    for lane, g in base.groupby("lane"):
        base.loc[g.index[0], "kg"] += demand[lane] - g["kg"].sum()
    base = base.drop(columns="share")

    lanes.to_csv(out / "lanes.csv", index=False)
    carriers.to_csv(out / "carriers.csv", index=False)
    offers.to_csv(out / "offers.csv", index=False)
    base.to_csv(out / "baseline.csv", index=False)
    return {"lanes": len(lanes), "carriers": len(carriers), "offers": len(offers), "total_kg": int(demand.sum())}
