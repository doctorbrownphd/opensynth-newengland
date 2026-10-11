"""Generate training dataset from the v0 mock model.

Produces ~500k daily load profiles covering the full conditioning space,
including day type (weekday/weekend/holiday).
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from opensynth_ne.archetypes import ARCHETYPES, DER_CONFIGS, FUELS
from opensynth_ne.model import COMPONENT_CHANNELS, generate_day
from opensynth_ne.weather import MONTH_IRRADIANCE, MONTH_TEMP_F

SAMPLES_PER_COMBO = 145  # ~500k total across 3456 combos (1152 x 3 day types)
N_CHANNELS = len(COMPONENT_CHANNELS)
N_TIMESTEPS = 96
OUTPUT_DIR = Path(__file__).parent / "data"

ARCH_IDS = [a.id for a in ARCHETYPES]
FUEL_IDS = [f.id for f in FUELS]
DER_IDS = [d.id for d in DER_CONFIGS]
DAY_TYPES = ["weekday", "weekend", "holiday"]
ARCH_TO_IDX = {a: i for i, a in enumerate(ARCH_IDS)}
FUEL_TO_IDX = {f: i for i, f in enumerate(FUEL_IDS)}
DAY_TYPE_TO_IDX = {d: i for i, d in enumerate(DAY_TYPES)}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    combos = []
    for a in ARCHETYPES:
        for f in FUELS:
            for d in DER_CONFIGS:
                for m in range(12):
                    for dt in DAY_TYPES:
                        combos.append((a, f, d, m, dt))

    n_combos = len(combos)
    n_total = n_combos * SAMPLES_PER_COMBO
    print(f"Generating {n_total:,} profiles across {n_combos} combos "
          f"({SAMPLES_PER_COMBO} samples each)")

    profiles = np.zeros((n_total, N_CHANNELS, N_TIMESTEPS), dtype=np.float32)
    # Conditions: arch_idx, fuel_idx, ev, solar, battery, month_sin, month_cos,
    #             temp_f, irradiance, scale, e_heat, day_type_idx
    N_COND = 12
    conditions = np.zeros((n_total, N_COND), dtype=np.float32)

    rng = np.random.default_rng(42)
    idx = 0
    t0 = time.time()

    for combo_i, (arch, fuel, der, month, day_type) in enumerate(combos):
        base_temp = MONTH_TEMP_F[month]
        irr = MONTH_IRRADIANCE[month]

        for s in range(SAMPLES_PER_COMBO):
            temp_f = base_temp + rng.normal(0, 7)
            temp_f = max(-10, min(100, temp_f))
            seed = combo_i * 10000 + s

            df, _ = generate_day(
                archetype=arch.id,
                fuel=fuel.id,
                month=month,
                temp_f=temp_f,
                has_ev=der.ev,
                has_solar=der.solar,
                has_battery=der.battery,
                day_type=day_type,
                seed=seed,
                use_cvae=False,
            )

            for ch_i, ch_name in enumerate(COMPONENT_CHANNELS):
                profiles[idx, ch_i, :] = df[ch_name].values

            month_rad = 2 * math.pi * month / 12
            conditions[idx] = [
                ARCH_TO_IDX[arch.id],
                FUEL_TO_IDX[fuel.id],
                float(der.ev),
                float(der.solar),
                float(der.battery),
                math.sin(month_rad),
                math.cos(month_rad),
                temp_f,
                irr,
                arch.scale,
                fuel.e_heat,
                DAY_TYPE_TO_IDX[day_type],
            ]
            idx += 1

        if (combo_i + 1) % 200 == 0:
            elapsed = time.time() - t0
            pct = (combo_i + 1) / n_combos * 100
            rate = idx / elapsed
            eta = (n_total - idx) / rate if rate > 0 else 0
            print(f"  {pct:.0f}% ({idx:,} profiles) — {rate:.0f}/s — ETA {eta:.0f}s")

    elapsed = time.time() - t0
    print(f"\nGenerated {idx:,} profiles in {elapsed:.1f}s ({idx/elapsed:.0f}/s)")

    # Normalization stats
    temp_f_vals = conditions[:idx, 7]
    scale_vals = conditions[:idx, 9]
    profile_means = profiles[:idx].mean(axis=(0, 2))
    profile_stds = profiles[:idx].std(axis=(0, 2))

    meta = {
        "n_samples": idx,
        "n_channels": N_CHANNELS,
        "n_timesteps": N_TIMESTEPS,
        "component_names": list(COMPONENT_CHANNELS),
        "condition_names": [
            "arch_idx", "fuel_idx", "has_ev", "has_solar", "has_battery",
            "month_sin", "month_cos", "temp_f", "irradiance", "scale", "e_heat",
            "day_type_idx",
        ],
        "n_conditions": N_COND,
        "arch_ids": ARCH_IDS,
        "fuel_ids": FUEL_IDS,
        "der_ids": DER_IDS,
        "day_types": DAY_TYPES,
        "temp_f_mean": float(temp_f_vals.mean()),
        "temp_f_std": float(temp_f_vals.std()),
        "scale_mean": float(scale_vals.mean()),
        "scale_std": float(scale_vals.std()),
        "profile_means": profile_means.tolist(),
        "profile_stds": profile_stds.tolist(),
    }

    np.save(OUTPUT_DIR / "profiles.npy", profiles[:idx])
    np.save(OUTPUT_DIR / "conditions.npy", conditions[:idx])
    with open(OUTPUT_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    file_size = (OUTPUT_DIR / "profiles.npy").stat().st_size / 1e6
    print(f"\nSaved to {OUTPUT_DIR}/")
    print(f"  profiles.npy:   {profiles[:idx].shape} — {file_size:.0f} MB")
    print(f"  conditions.npy: {conditions[:idx].shape}")
    print(f"  meta.json:      {len(meta)} keys")


if __name__ == "__main__":
    main()
