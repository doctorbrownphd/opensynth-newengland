"""Validation checks against regional statistics.

Pre-computed reference values for the v0 mock model, gating each dataset
release against independently verifiable sources (EIA RECS, ISO-NE, NREL).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from opensynth_ne.model import _mulberry32


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    """One validation check comparing synthetic output to a regional target."""

    id: str
    metric: str
    source: str
    target: str
    target_val: float
    synth_val: float
    unit: str
    delta: float | None
    passing: bool


CHECKS: tuple[ValidationCheck, ...] = (
    ValidationCheck(
        "kwh", "Annual kWh distribution", "EIA RECS — NE residential",
        "within 5% of reported mean", 8460, 8788, "kWh/yr", 3.9, True,
    ),
    ValidationCheck(
        "wpeak", "Winter peak timing", "ISO-NE published peak data",
        "within 1 hour of regional", 18.25, 18.75, "h", 0.5, True,
    ),
    ValidationCheck(
        "shape", "Summer load-shape correlation", "ISO-NE shoulder load",
        "shape correlation > 0.85", 0.85, 0.91, "r", None, True,
    ),
    ValidationCheck(
        "ev", "EV charging signature", "Published EV charging studies",
        "peak window 23:00-04:00", 1.5, 1.25, "h offset", None, True,
    ),
    ValidationCheck(
        "pv", "Solar generation shape", "NREL PVWatts regional",
        "within 10% of modeled output", 100, 107.5, "% modeled", 7.5, True,
    ),
    ValidationCheck(
        "wkwh", "Winter monthly kWh (oil-heat homes)", "EIA RECS — NE oil",
        "within 8% of reported", 1180, 850, "kWh", 28.0, False,
    ),
)


def validate() -> list[ValidationCheck]:
    """Return all validation checks with their results."""
    return list(CHECKS)


def distribution(seed: int, mean: float, spread: float, n_bins: int) -> list[int]:
    """Generate a histogram using Box-Muller transform with seeded RNG.

    Produces 4000 Gaussian samples from N(mean, spread) and bins them
    into n_bins buckets spanning [mean - 3*spread, mean + 3*spread].

    Exact port of the data.js distribution() function.
    """
    r = _mulberry32(seed)
    bins = [0] * n_bins
    lo = mean - 3 * spread
    span = 6 * spread

    for _ in range(4000):
        # Box-Muller transform
        u = 0.0
        while u == 0.0:
            u = r()
        v = 0.0
        while v == 0.0:
            v = r()
        g = math.sqrt(-2 * math.log(u)) * math.cos(6.283 * v)
        x = mean + g * spread
        b = int((x - lo) / span * n_bins)
        b = max(0, min(n_bins - 1, b))
        bins[b] += 1

    return bins
