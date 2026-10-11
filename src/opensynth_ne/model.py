"""Synthetic load profile model.

Supports two backends:
  - v0 mock: deterministic formulas (always available)
  - CVAE: trained conditional VAE (when weights are installed)

The public API (generate_day, generate) auto-detects which backend to use.
Pass use_cvae=True/False to override.
"""

from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from opensynth_ne.archetypes import (
    ARCHETYPES,
    Archetype,
    DER_CONFIGS,
    FUELS,
    FuelType,
    get_archetype,
    get_fuel,
)
from opensynth_ne.weather import (
    MONTH_IRRADIANCE,
    MONTH_TEMP_F,
    cooling_intensity,
    heating_intensity,
)

# ---------------------------------------------------------------------------
# Seeded RNG — exact port of mulberry32 + FNV-1a from data.js
# ---------------------------------------------------------------------------

_U32 = 0xFFFFFFFF


def _mulberry32(seed: int) -> Callable[[], float]:
    """Mulberry32 seeded PRNG. Returns a callable producing floats in [0, 1)."""
    state = [seed & _U32]

    def next_float() -> float:
        a = (state[0] + 0x6D2B79F5) & _U32
        state[0] = a
        t = ((a ^ (a >> 15)) * (1 | a)) & _U32
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & _U32)) & _U32) ^ t
        return ((t ^ (t >> 14)) & _U32) / 4294967296

    return next_float


def _hash_str(s: str) -> int:
    """FNV-1a hash of a string, returning an unsigned 32-bit integer."""
    h = 2166136261
    for c in s:
        h = (h ^ ord(c)) & _U32
        h = (h * 16777619) & _U32
    return h


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _bump(h: float, center: float, width: float) -> float:
    """Gaussian bump: exp(-0.5 * ((h - center) / width)^2)."""
    x = (h - center) / width
    return math.exp(-0.5 * x * x)


def _heatpump_cop_factor(temp_f: float) -> float:
    """Heat pump COP degradation with partial-heating switchover blend.

    Based on ISO-NE Final 2024 Heating Electrification Forecast (§5.6):
    - Space-heating onset: 62°F outdoor
    - Switchover blend: normal distribution, mean 20°F, std 5°F
    - Below switchover: electric resistance backup (COP=1.0, higher draw)

    The blend means not all homes switch at the same temperature —
    some switch at 25°F, others at 15°F — removing the unrealistic
    synchronized load cliff that a single-temperature model produces.
    """
    if temp_f >= 47:
        return 1.0
    # Above switchover zone: gradual COP decline (NEEP data)
    if temp_f > 30:
        return 1.0 + 0.3 * (47.0 - temp_f) / 17.0
    # Switchover blend zone (20°F ± 2σ = 10-30°F):
    # Fraction of homes on backup resistance increases as temp drops
    # Normal CDF approximation: at 20°F, 50% on backup; at 10°F, ~98%
    z = (20.0 - temp_f) / 5.0  # standard deviations below switchover mean
    # Sigmoid approximation of normal CDF
    backup_frac = 1.0 / (1.0 + math.exp(-1.7 * z))
    # Blended COP: backup homes at 1.0 COP (resistance), rest at degraded HP COP
    hp_cop_factor = 1.3 + 0.4 * max(0.0, (30.0 - temp_f) / 40.0)
    return (1.0 - backup_frac) * hp_cop_factor + backup_frac * 2.0


def _cloud_cover(h: float, seed: int, month: int) -> float:
    """Stochastic cloud attenuation factor [0.2, 1.0] for solar generation.

    Uses seeded RNG for consistent cloud patterns per meter-day.
    Winter months are cloudier than summer (NE climate).
    """
    # Prime 997 decorrelates cloud RNG from the main interval RNG
    r = _mulberry32(seed + month * 997)
    seasonal_clear = 0.35 + 0.25 * (1.0 - abs(month - 6) / 6.0)

    day_roll = r()
    if day_roll < seasonal_clear:
        return max(0.85, 1.0 - 0.15 * r())
    elif day_roll < seasonal_clear + 0.35:
        atten = 1.0
        for _ in range(2 + int(r() * 2)):
            cloud_center = 8.0 + r() * 9.0
            cloud_width = 0.5 + r() * 1.5
            atten *= 1.0 - 0.5 * _bump(h, cloud_center, cloud_width)
        return max(0.2, atten)
    else:
        return 0.25 + 0.15 * r()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INTERVAL_COUNT = 96
_COLUMNS = ("interval", "hour", "net", "gross", "base", "heat", "ev", "cool", "solar", "behav")

# Behavioral load timing modifiers by day type.
_DAY_MODS = {
    "weekday": {"morn_h": 7.0, "morn_a": 0.55, "eve_h": 18.5, "eve_a": 0.95, "mid_a": 0.20},
    "weekend": {"morn_h": 9.0, "morn_a": 0.45, "eve_h": 19.5, "eve_a": 0.85, "mid_a": 0.40},
    "holiday": {"morn_h": 9.5, "morn_a": 0.40, "eve_h": 19.0, "eve_a": 0.80, "mid_a": 0.45},
}
_VALID_DAY_TYPES = frozenset(_DAY_MODS.keys())

# Load component channel names — training contract, do not reorder without retraining CVAE.
COMPONENT_CHANNELS = ("base", "behav", "heat", "cool", "ev", "solar")


# ---------------------------------------------------------------------------
# #2: Typed meter perturbation — replaces untyped dict
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MeterPerturbation:
    """Per-meter variation parameters for household-level diversity.

    All factors are seeded deterministically from meter_id so the same
    meter always gets the same perturbation.
    """

    sqft_factor: float       # [0.80, 1.20] — house size within archetype range
    timing_offset: float     # [-0.75, +0.75] hours — schedule variation
    thermostat_offset: float  # [-4.0, +4.0] °F — setpoint preference
    occupancy_factor: float  # [0.70, 1.30] — 1-4 person household
    appliance_age: float     # [0.85, 1.15] — older appliances draw more
    insulation_factor: float  # [0.80, 1.20] — envelope quality
    ev_charge_rate: float    # [0.70, 1.00] — L1/L2 mix
    cloud_seed: int          # deterministic cloud pattern

    @classmethod
    def random(cls, meter_id: int, base_seed: int) -> MeterPerturbation:
        """Generate seeded random perturbation for a meter."""
        # Prime 7919 spreads meter IDs across the RNG state space
        r = _mulberry32(base_seed + meter_id * 7919)
        return cls(
            sqft_factor=0.80 + r() * 0.40,
            timing_offset=(r() - 0.5) * 1.5,
            thermostat_offset=(r() - 0.5) * 8.0,
            occupancy_factor=0.7 + r() * 0.6,
            appliance_age=0.85 + r() * 0.30,
            insulation_factor=0.8 + r() * 0.4,
            ev_charge_rate=0.7 + r() * 0.3,
            cloud_seed=int(r() * 100000),
        )

    @classmethod
    def identity(cls) -> MeterPerturbation:
        """No perturbation — all factors at neutral."""
        return cls(1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0)


# ---------------------------------------------------------------------------
# #1: Shared load component core — single source of truth for physics
# ---------------------------------------------------------------------------


def _compute_components(
    h: float,
    arch: Archetype,
    fl: FuelType,
    temp: float,
    irr: float,
    hdd: float,
    cdd: float,
    day_type: str,
    has_ev: bool,
    has_ev_managed: bool,
    has_solar: bool,
    seed: int,
    month: int,
    noise_val: float,
    pert: MeterPerturbation,
) -> tuple[float, float, float, float, float, float]:
    """Compute one interval's 6 load components (kW).

    Returns (base, behav, heat, cool, ev, solar).
    This is THE single source of truth for the mock load model physics.
    Both generate_day() and _compute_intervals() call this.
    """
    scale = arch.scale * pert.sqft_factor
    to = pert.timing_offset
    occ = pert.occupancy_factor
    adj_temp = temp + pert.thermostat_offset
    adj_hdd = heating_intensity(adj_temp)
    adj_cdd = cooling_intensity(adj_temp)
    dm = _DAY_MODS[day_type]

    # --- baseload: fridge, standby, lighting, hot water, dryer, cooking, misc ---
    lighting_seasonal = 1.0 + 0.08 * hdd
    base = ((0.38 + 0.12 * scale)
            * (0.92 + 0.16 * math.sin(h / 24 * 6.283 + 1))
            * lighting_seasonal * occ * pert.appliance_age)

    # --- behavioral: morning + evening human activity ---
    behav = scale * occ * (
        dm["morn_a"] * _bump(h, dm["morn_h"] + to, 1.3)
        + dm["eve_a"] * _bump(h, dm["eve_h"] + to, 2.2)
        + dm["mid_a"] * _bump(h, 12.5 + to, 1.6)
    )

    # --- electric heating (scaled by insulation: poor → more heating) ---
    heat = (
        fl.e_heat * adj_hdd * scale * (1.0 / pert.insulation_factor)
        * (1.7 * _bump(h, 6.5 + to, 2.4) + 2.1 * _bump(h, 19 + to, 3.0) + 0.7)
    )
    if fl.id == "heatpump":
        heat *= _heatpump_cop_factor(adj_temp)

    # --- cooling (also insulation-sensitive) ---
    cool = adj_cdd * scale * (1.0 / pert.insulation_factor) * 1.3 * _bump(h, 16.5, 3.0)

    # --- EV charging ---
    ev = 0.0
    if has_ev:
        charge_kw = 6.6 * pert.ev_charge_rate
        if has_ev_managed:
            if 23 <= h or h < 4.75:
                ev = charge_kw
            elif 4.75 <= h < 5.0:
                ev = charge_kw * (5.0 - h) / 0.25
            elif 22.75 <= h < 23:
                ev = charge_kw * (h - 22.75) / 0.25
        else:
            ev = (charge_kw * 1.09) * _bump(h, 18.5 + to, 1.5) + (3.0 if 18 <= h < 22 else 0.0)

    # --- solar PV (negative = generation) ---
    solar = 0.0
    if has_solar:
        day_shape = _bump(h, 12.6, 3.1)
        cloud = _cloud_cover(h, pert.cloud_seed if pert.cloud_seed else seed, month)
        solar = -(5.2 * scale * irr * cloud) * (day_shape if 6.5 < h < 19 else 0.0)

    return base, behav, heat, cool, max(0.0, ev), solar


def _assemble_interval(
    i: int,
    base: float,
    behav: float,
    heat: float,
    cool: float,
    ev: float,
    solar: float,
    has_battery: bool,
    has_solar: bool,
    irr: float,
    noise_val: float,
) -> tuple:
    """Assemble one interval from components → (net, gross, base, heat, ev, cool, solar, behav).

    Battery dispatch is deterministic and applied here (not learned by CVAE).
    """
    h = i * 0.25
    batt = 0.0
    if has_battery:
        if has_solar and 10 < h < 14:
            batt = 1.6 * irr
        elif 17.5 < h < 21:
            batt = -1.8

    gross = max(0.05, base + behav + heat + cool + ev + max(0.0, batt) + noise_val)
    net = gross + solar + (batt if batt < 0 else 0.0)

    return (
        round(net, 3), round(gross, 3), round(base, 3), round(heat, 3),
        round(ev, 3), round(cool, 3), round(solar, 3), round(behav, 3),
    )


def _build_day_df(rows: list[tuple]) -> tuple[pd.DataFrame, dict]:
    """Build a DataFrame and summary dict from 96 assembled interval tuples."""
    full_rows = []
    for i, vals in enumerate(rows):
        full_rows.append((i, round(i * 0.25, 2), *vals))

    df = pd.DataFrame(full_rows, columns=list(_COLUMNS))
    net_series = df["net"]
    peak_idx = int(net_series.idxmax())
    summary = {
        "temp": 0.0,  # caller sets this
        "irr": 0.0,
        "peak": float(net_series.max()),
        "peak_hour": float(df.loc[peak_idx, "hour"]),
        "min": float(net_series.min()),
        "kwh": round(float(net_series.sum()) * 0.25, 1),
    }
    return df, summary


# ---------------------------------------------------------------------------
# CVAE auto-detection
# ---------------------------------------------------------------------------

_WEIGHTS_DIR = pathlib.Path(__file__).parent / "weights"
_cvae_available: bool | None = None


def _check_cvae() -> bool:
    """Check if trained CVAE weights exist and torch is importable."""
    global _cvae_available
    if _cvae_available is None:
        if not (_WEIGHTS_DIR / "best_model.pt").exists():
            _cvae_available = False
        else:
            try:
                import torch  # noqa: F401
                _cvae_available = True
            except ImportError:
                _cvae_available = False
    return _cvae_available


def _generate_day_cvae(
    archetype: str, fuel: str, month: int, temp_f: float | None,
    has_ev: bool, has_solar: bool, has_battery: bool,
    has_ev_managed: bool, seed: int,
) -> tuple[pd.DataFrame, dict]:
    """Generate a day using the trained CVAE, with shared post-processing."""
    from opensynth_ne.cvae_inference import CVAEGenerator

    gen = CVAEGenerator.get()
    components = gen.generate_day(
        archetype=archetype, fuel=fuel, month=month, temp_f=temp_f,
        has_ev=has_ev, has_solar=has_solar, has_battery=has_battery, seed=seed,
    )

    temp = MONTH_TEMP_F[month] if temp_f is None else temp_f
    irr = MONTH_IRRADIANCE[month]

    rows = []
    for i in range(_INTERVAL_COUNT):
        base = float(max(0, components[0, i]))
        behav = float(max(0, components[1, i]))
        heat = float(max(0, components[2, i]))
        cool = float(max(0, components[3, i]))
        ev = float(max(0, components[4, i])) if has_ev else 0.0
        solar = float(min(0, components[5, i])) if has_solar else 0.0

        vals = _assemble_interval(i, base, behav, heat, cool, ev, solar,
                                   has_battery, has_solar, irr, 0.0)
        rows.append(vals)

    df, summary = _build_day_df(rows)
    summary["temp"] = temp
    summary["irr"] = irr
    return df, summary


# ---------------------------------------------------------------------------
# generate_day — public API
# ---------------------------------------------------------------------------


def generate_day(
    archetype: str = "colonial",
    fuel: str = "oil",
    month: int = 0,
    temp_f: float | None = None,
    has_ev: bool = False,
    has_solar: bool = False,
    has_battery: bool = False,
    has_ev_managed: bool = True,
    day_type: str = "weekday",
    seed: int = 42,
    use_cvae: bool | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Generate one day of 15-minute interval load data (96 intervals).

    Parameters
    ----------
    day_type : "weekday", "weekend", or "holiday"
    use_cvae : None = auto-detect, True = force CVAE, False = force mock

    Returns
    -------
    df : DataFrame with 96 rows (interval, hour, net, gross, base, heat, ev, cool, solar, behav)
    summary : dict with keys temp, irr, peak, peak_hour, min, kwh
    """
    if not 0 <= month <= 11:
        raise ValueError(f"month must be in [0, 11], got {month}")
    if day_type not in _VALID_DAY_TYPES:
        raise ValueError(f"day_type must be one of {sorted(_VALID_DAY_TYPES)}, got '{day_type}'")
    get_archetype(archetype)
    get_fuel(fuel)

    if use_cvae is None:
        use_cvae = _check_cvae()
    if use_cvae:
        return _generate_day_cvae(
            archetype, fuel, month, temp_f,
            has_ev, has_solar, has_battery, has_ev_managed, seed,
        )

    arch = get_archetype(archetype)
    fl = get_fuel(fuel)
    temp = MONTH_TEMP_F[month] if temp_f is None else temp_f
    irr = MONTH_IRRADIANCE[month]
    hdd = heating_intensity(temp)
    cdd = cooling_intensity(temp)
    r = _mulberry32(seed + _hash_str(archetype + fuel + str(month)))
    pert = MeterPerturbation.identity()

    rows = []
    for i in range(_INTERVAL_COUNT):
        h = i * 0.25
        noise = (r() - 0.5) * 0.18 * arch.scale

        comps = _compute_components(
            h, arch, fl, temp, irr, hdd, cdd, day_type,
            has_ev, has_ev_managed, has_solar, seed, month, noise, pert,
        )
        vals = _assemble_interval(i, *comps, has_battery, has_solar, irr, noise)
        rows.append(vals)

    df, summary = _build_day_df(rows)
    summary["temp"] = temp
    summary["irr"] = irr
    return df, summary


# ---------------------------------------------------------------------------
# generate_year
# ---------------------------------------------------------------------------


def _day_type_from_doy(day_of_year: int) -> str:
    """Infer weekday/weekend/holiday from day-of-year (0-364)."""
    _HOLIDAYS = {0, 20, 51, 148, 185, 249, 283, 314, 327, 359}
    if day_of_year in _HOLIDAYS:
        return "holiday"
    weekday = (day_of_year + 2) % 7
    return "weekend" if weekday >= 5 else "weekday"


def generate_year(
    archetype: str = "colonial",
    fuel: str = "oil",
    has_ev: bool = False,
    has_solar: bool = False,
    has_battery: bool = False,
    has_ev_managed: bool = True,
    seed: int = 7,
) -> list[dict]:
    """Generate 365-day peak/kwh/temp series for a single meter."""
    out: list[dict] = []
    for d in range(365):
        m = min(11, int(d / 30.4))
        dt = _day_type_from_doy(d)
        wr = _mulberry32(1000 + d + _hash_str(archetype + fuel))
        t = MONTH_TEMP_F[m] + (wr() - 0.5) * 14

        _, summary = generate_day(
            archetype=archetype, fuel=fuel, month=m, temp_f=t,
            has_ev=has_ev, has_solar=has_solar, has_battery=has_battery,
            has_ev_managed=has_ev_managed, day_type=dt, seed=d + 7,
        )
        out.append({
            "d": d, "m": m,
            "peak": round(summary["peak"], 2),
            "kwh": round(summary["kwh"], 1),
            "temp": round(t, 1),
            "min": round(summary["min"], 2),
            "day_type": dt,
        })
    return out


# ---------------------------------------------------------------------------
# generate — batch: n meters x full year (or single month)
# ---------------------------------------------------------------------------

_BATCH_COLUMNS = (
    "meter_id", "archetype", "fuel", "der",
    "day_of_year", "month", "interval", "hour",
    "net", "gross", "base", "heat", "ev", "cool", "solar", "behav",
)


def _build_catalog_weights(seed: int = 0) -> list[tuple[str, str, str, bool, bool, bool, float]]:
    """Build the 96 base-type catalog with empirical NE housing stock weights.

    Archetype and fuel weights derived from Census ACS B25024 (structure type)
    and B25040 (heating fuel) for 47 towns in southern New Hampshire and
    north-central Massachusetts, scaled to ISO-NE regional proportions.
    """
    # Archetype weights from NE structure type distribution (ACS B25024)
    # SF detached ~58%, SF attached ~5%, 2-4 unit ~17%, 5+ unit ~17%, mobile ~3%
    _ARCH_WEIGHTS = {
        "colonial": 0.18,      # larger SF detached
        "cape": 0.16,          # mid-size SF detached
        "ranch": 0.14,         # mid-size SF detached
        "splitlevel": 0.07,    # SF detached variant
        "contemporary": 0.05,  # newer SF detached
        "antique": 0.08,       # pre-1940 SF (33.6% of Concord stock)
        "multifamily": 0.28,   # 2-4 unit + 5+ unit combined
        "mobilehome": 0.04,    # mobile homes
    }
    # Fuel weights from NE territory B25040 (averaged across 47 towns)
    # Oil 40%, gas 27%, electric 12%, propane 15%, wood 4%, other 2%
    _FUEL_WEIGHTS = {
        "oil": 0.40,
        "gas": 0.27,
        "electric": 0.12,
        "heatpump": 0.21,  # electric + propane-to-HP conversions trending
    }
    # DER weights (approximate NE penetration rates 2024)
    _DER_WEIGHTS = {"none": 0.82, "solar": 0.13, "solar_ev": 0.05}

    entries = []
    total = 0.0
    for a in ARCHETYPES:
        for f in FUELS:
            for d in DER_CONFIGS:
                w = _ARCH_WEIGHTS.get(a.id, 0.1) * _FUEL_WEIGHTS.get(f.id, 0.25) * _DER_WEIGHTS.get(d.id, 0.33)
                # Add small random perturbation for variation across base types
                r = _mulberry32(_hash_str(a.id + f.id + d.id))
                w *= (0.8 + r() * 0.4)  # ±20% noise
                entries.append((a.id, f.id, d.id, d.ev, d.solar, d.battery, w))
                total += w
    return [(a, f, d, ev, sol, bat, w / total) for a, f, d, ev, sol, bat, w in entries]


# #3: Public catalog function — seals the RNG leak from api.py
def build_catalog() -> list[dict]:
    """Build the 96 base-type catalog with sparkline data.

    Public API for the catalog endpoint — callers don't need internal RNG access.
    """
    rows = []
    for a in ARCHETYPES:
        for f in FUELS:
            for d in DER_CONFIGS:
                r = _mulberry32(_hash_str(a.id + f.id + d.id))
                count = round(40 + r() * 180)

                day_df, _ = generate_day(
                    archetype=a.id, fuel=f.id, month=0,
                    has_ev=d.ev, has_solar=d.solar, has_battery=d.battery,
                    seed=_hash_str(a.id + "-" + f.id + "-" + d.id) % 9999,
                )
                sparkline = day_df.iloc[::4]["net"].round(2).tolist()

                rows.append({
                    "id": f"{a.id}-{f.id}-{d.id}",
                    "archetype": a.id, "archetype_label": a.label,
                    "fuel": f.id, "fuel_label": f.label,
                    "der": d.id, "der_label": d.label,
                    "ev": d.ev, "solar": d.solar, "battery": d.battery,
                    "count": count, "sparkline": sparkline,
                })
    return rows


def generate(
    n: int = 100,
    archetype: str | None = "colonial",
    fuel: str | None = "oil",
    month: int | None = None,
    temp_f: float | None = None,
    has_ev: bool = False,
    has_solar: bool = False,
    has_battery: bool = False,
    has_ev_managed: bool = True,
    distribution: str = "empirical",
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic load profiles for n meters.

    Parameters
    ----------
    n : Number of synthetic meters.
    archetype, fuel : Fix all meters to one base type, or None to distribute.
    month : 0-11 for single day, or None for full year (365 days).
    distribution : "empirical" or "uniform".
    seed : Fixed seed for reproducibility. None for random.
    """
    if seed is None:
        seed = int(np.random.default_rng().integers(0, 2**31))

    # Allocate meters to base types
    if archetype is not None and fuel is not None:
        der_id = "none"
        for d in DER_CONFIGS:
            if d.ev == has_ev and d.solar == has_solar and d.battery == has_battery:
                der_id = d.id
                break
        assignments = [(archetype, fuel, der_id, has_ev, has_solar, has_battery)] * n
    else:
        catalog = _build_catalog_weights(seed)
        weights = ([1.0 / len(catalog)] * len(catalog) if distribution == "uniform"
                   else [e[6] for e in catalog])
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

        alloc_rng = _mulberry32(seed + 9999)
        assignments = []
        for _ in range(n):
            rv = alloc_rng()
            cumulative = 0.0
            for idx, w in enumerate(weights):
                cumulative += w
                if rv < cumulative:
                    e = catalog[idx]
                    assignments.append((e[0], e[1], e[2], e[3], e[4], e[5]))
                    break
            else:
                e = catalog[-1]
                assignments.append((e[0], e[1], e[2], e[3], e[4], e[5]))

    # Generate intervals for each meter
    days_range = range(365) if month is None else [0]
    all_rows: list[tuple] = []

    for meter_idx, (m_arch, m_fuel, m_der, m_ev, m_solar, m_batt) in enumerate(assignments):
        meter_id = f"meter_{meter_idx:05d}"
        pert = MeterPerturbation.random(meter_idx, seed)
        arch = get_archetype(m_arch)
        fl = get_fuel(m_fuel)

        for d_offset in days_range:
            if month is None:
                m = min(11, int(d_offset / 30.4))
                wr = _mulberry32(1000 + d_offset + _hash_str(m_arch + m_fuel) + meter_idx)
                day_temp = MONTH_TEMP_F[m] + (wr() - 0.5) * 14
                day_seed = d_offset + 7
                dt = _day_type_from_doy(d_offset)
            else:
                m = month
                day_temp = temp_f if temp_f is not None else MONTH_TEMP_F[m]
                day_seed = seed
                dt = "weekday"

            irr = MONTH_IRRADIANCE[m]
            hdd = heating_intensity(day_temp)
            cdd = cooling_intensity(day_temp)
            r = _mulberry32(day_seed + meter_idx + _hash_str(m_arch + m_fuel + str(m)))

            for i in range(_INTERVAL_COUNT):
                h = i * 0.25
                noise = (r() - 0.5) * 0.18 * arch.scale * pert.sqft_factor

                comps = _compute_components(
                    h, arch, fl, day_temp, irr, hdd, cdd, dt,
                    m_ev, has_ev_managed, m_solar, day_seed + meter_idx, m, noise, pert,
                )
                vals = _assemble_interval(i, *comps, m_batt, m_solar, irr, noise)

                all_rows.append((
                    meter_id, m_arch, m_fuel, m_der,
                    d_offset, m, i, round(h, 2), *vals,
                ))

    return pd.DataFrame(all_rows, columns=list(_BATCH_COLUMNS))
