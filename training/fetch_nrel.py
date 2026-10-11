"""Fetch NREL ResStock End-Use Load Profiles for New England states.

Downloads individual building parquet files from the OEDI S3 data lake
(public, no auth required) and processes them into our 6-component
training format.

Usage:
    python training/fetch_nrel.py                    # default: 50 buildings per state
    python training/fetch_nrel.py --per-state 200    # more buildings
    python training/fetch_nrel.py --states NH MA     # specific states only
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from opensynth_ne.model import COMPONENT_CHANNELS
from opensynth_ne.weather import MONTH_IRRADIANCE, MONTH_TEMP_F

OUTPUT_DIR = Path(__file__).parent / "reference_data" / "nrel"
S3_BASE = "s3://oedi-data-lake/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2024/resstock_amy2018_release_2"

NE_STATES = ["CT", "MA", "ME", "NH", "RI", "VT"]

# Map NREL end-use columns to our 6 component channels
COMPONENT_MAP = {
    "base": [
        "out.electricity.refrigerator.energy_consumption",
        "out.electricity.freezer.energy_consumption",
        "out.electricity.plug_loads.energy_consumption",
        "out.electricity.lighting_interior.energy_consumption",
        "out.electricity.lighting_exterior.energy_consumption",
        "out.electricity.lighting_garage.energy_consumption",
        "out.electricity.ceiling_fan.energy_consumption",
        "out.electricity.mech_vent.energy_consumption",
        "out.electricity.permanent_spa_heat.energy_consumption",
        "out.electricity.permanent_spa_pump.energy_consumption",
        "out.electricity.pool_heater.energy_consumption",
        "out.electricity.pool_pump.energy_consumption",
    ],
    "behav": [
        "out.electricity.range_oven.energy_consumption",
        "out.electricity.dishwasher.energy_consumption",
        "out.electricity.clothes_dryer.energy_consumption",
        "out.electricity.clothes_washer.energy_consumption",
        "out.electricity.hot_water.energy_consumption",
    ],
    "heat": [
        "out.electricity.heating.energy_consumption",
        "out.electricity.heating_fans_pumps.energy_consumption",
        "out.electricity.heating_hp_bkup.energy_consumption",
        "out.electricity.heating_hp_bkup_fa.energy_consumption",
    ],
    "cool": [
        "out.electricity.cooling.energy_consumption",
        "out.electricity.cooling_fans_pumps.energy_consumption",
    ],
    "ev": [
        "out.electricity.vehicle.energy_consumption",
    ],
    "solar": [
        "out.electricity.pv.energy_consumption",
    ],
}


def list_buildings(state: str) -> list[str]:
    """List available building parquet files for a state via AWS CLI."""
    prefix = f"{S3_BASE}/timeseries_individual_buildings/by_state/upgrade=0/state={state}/"
    result = subprocess.run(
        ["aws", "s3", "ls", "--no-sign-request", prefix],
        capture_output=True, text=True, timeout=30,
    )
    files = []
    for line in result.stdout.strip().split("\n"):
        if line.strip() and line.strip().endswith(".parquet"):
            fname = line.strip().split()[-1]
            files.append(fname)
    return files


def download_building(state: str, filename: str, dest_dir: Path) -> Path:
    """Download one building parquet file."""
    s3_path = f"{S3_BASE}/timeseries_individual_buildings/by_state/upgrade=0/state={state}/{filename}"
    local_path = dest_dir / f"{state}_{filename}"
    if local_path.exists():
        return local_path

    subprocess.run(
        ["aws", "s3", "cp", "--no-sign-request", s3_path, str(local_path)],
        capture_output=True, timeout=60,
    )
    return local_path


def process_building(parquet_path: Path) -> np.ndarray | None:
    """Process one building into (365, 6, 96) daily profiles.

    Returns None if the file is invalid or has insufficient data.
    """
    try:
        df = pd.read_parquet(parquet_path)
    except Exception:
        return None

    if len(df) < 35040:
        return None

    # Sum NREL columns into our 6 components
    component_series = {}
    for comp_name, nrel_cols in COMPONENT_MAP.items():
        available = [c for c in nrel_cols if c in df.columns]
        if available:
            component_series[comp_name] = df[available].sum(axis=1).values
        else:
            component_series[comp_name] = np.zeros(len(df))

    # Convert from kWh per 15-min interval to kW (power)
    # NREL data is in kWh per timestep, so multiply by 4 to get kW
    for key in component_series:
        component_series[key] = component_series[key] * 4.0

    # Solar is generation (should be negative in our convention)
    component_series["solar"] = -np.abs(component_series["solar"])

    # Reshape into (365, 6, 96) — 365 days × 6 channels × 96 intervals
    n_days = len(df) // 96
    if n_days < 365:
        return None

    profiles = np.zeros((365, 6, 96), dtype=np.float32)
    for ch_idx, ch_name in enumerate(COMPONENT_CHANNELS):
        data = component_series[ch_name][:365 * 96]
        profiles[:, ch_idx, :] = data.reshape(365, 96)

    return profiles


def infer_conditions(parquet_path: Path, profiles: np.ndarray) -> list[dict]:
    """Infer conditioning variables from the profile data.

    Since we don't have NREL metadata here, we infer:
    - Month from day index
    - Temperature from monthly averages (NE)
    - Archetype/fuel from load patterns
    """
    conditions = []
    for day_idx in range(365):
        month = min(11, int(day_idx / 30.4))
        day_profile = profiles[day_idx]  # (6, 96)

        # Infer heating fuel from electric heating share
        heat_total = day_profile[2].sum()  # heat channel
        total = day_profile.sum()
        e_heat_share = heat_total / max(total, 0.01)

        # Map to closest fuel type
        if e_heat_share > 0.4:
            fuel_idx = 2  # electric
        elif e_heat_share > 0.25:
            fuel_idx = 3  # heatpump
        elif e_heat_share > 0.10:
            fuel_idx = 0  # oil (some electric aux)
        else:
            fuel_idx = 1  # gas (minimal electric)

        # Infer archetype from daily kWh (scale proxy)
        daily_kwh = total * 0.25  # 15-min intervals → kWh
        if daily_kwh > 50:
            arch_idx = 0  # colonial (large)
        elif daily_kwh > 35:
            arch_idx = 4  # antique
        elif daily_kwh > 25:
            arch_idx = 2  # ranch
        elif daily_kwh > 18:
            arch_idx = 1  # cape
        else:
            arch_idx = 3  # multifamily (small)

        # DER flags from data
        has_ev = float(day_profile[4].max() > 0.5)  # EV channel
        has_solar = float(day_profile[5].min() < -0.1)  # solar channel (negative)
        has_battery = 0.0  # can't detect from NREL data

        # Temperature from NE monthly average + noise
        temp_f = MONTH_TEMP_F[month]
        irr = MONTH_IRRADIANCE[month]

        # Day type
        weekday = (day_idx + 2) % 7
        if weekday >= 5:
            day_type_idx = 1  # weekend
        else:
            day_type_idx = 0  # weekday

        month_rad = 2 * math.pi * month / 12
        # Approximate scale from archetype
        scales = [1.35, 1.0, 1.1, 0.7, 1.45, 1.15, 1.05, 0.85]
        e_heats = [0.25, 0.15, 1.0, 0.55]

        conditions.append([
            arch_idx, fuel_idx, has_ev, has_solar, has_battery,
            math.sin(month_rad), math.cos(month_rad),
            float(temp_f), irr, scales[arch_idx], e_heats[fuel_idx],
            float(day_type_idx),
        ])

    return conditions


def main():
    parser = argparse.ArgumentParser(description="Fetch NREL ResStock data for NE")
    parser.add_argument("--states", nargs="+", default=NE_STATES)
    parser.add_argument("--per-state", type=int, default=50)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = args.output_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    all_profiles = []
    all_conditions = []

    for state in args.states:
        print(f"\n--- {state} ---")
        buildings = list_buildings(state)
        print(f"  Available: {len(buildings)} buildings")

        n_download = min(args.per_state, len(buildings))
        success = 0

        for i, fname in enumerate(buildings[:n_download]):
            local_path = download_building(state, fname, raw_dir)
            profiles = process_building(local_path)

            if profiles is not None:
                conditions = infer_conditions(local_path, profiles)
                all_profiles.append(profiles)  # (365, 6, 96)
                all_conditions.extend(conditions)
                success += 1

            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{n_download} downloaded, {success} valid")

        print(f"  Done: {success}/{n_download} valid buildings")

    # Stack all profiles
    if not all_profiles:
        print("No valid buildings found!")
        return

    # Flatten: (N_buildings, 365, 6, 96) → (N_days, 6, 96)
    profiles_arr = np.concatenate(all_profiles, axis=0)  # (N*365, 6, 96)
    conditions_arr = np.array(all_conditions, dtype=np.float32)

    print(f"\n--- Summary ---")
    print(f"  Buildings: {len(all_profiles)}")
    print(f"  Day profiles: {profiles_arr.shape[0]:,}")
    print(f"  Conditions: {conditions_arr.shape}")

    # Compute stats
    profile_means = profiles_arr.mean(axis=(0, 2))
    profile_stds = profiles_arr.std(axis=(0, 2))
    temp_vals = conditions_arr[:, 7]

    meta = {
        "source": "NREL ResStock End-Use Load Profiles 2024",
        "states": args.states,
        "n_buildings": len(all_profiles),
        "n_day_profiles": int(profiles_arr.shape[0]),
        "n_channels": 6,
        "n_timesteps": 96,
        "component_names": list(COMPONENT_CHANNELS),
        "profile_means": profile_means.tolist(),
        "profile_stds": profile_stds.tolist(),
        "temp_f_mean": float(temp_vals.mean()),
        "temp_f_std": float(temp_vals.std()),
        "daily_kwh_mean": float(profiles_arr.sum(axis=(1, 2)).mean() * 0.25),
        "annual_kwh_est": float(profiles_arr.sum(axis=(1, 2)).mean() * 0.25 * 365),
    }

    # Save
    np.save(args.output_dir / "nrel_profiles.npy", profiles_arr)
    np.save(args.output_dir / "nrel_conditions.npy", conditions_arr)
    with open(args.output_dir / "nrel_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    size_mb = (args.output_dir / "nrel_profiles.npy").stat().st_size / 1e6
    print(f"\n  Saved to {args.output_dir}/")
    print(f"  nrel_profiles.npy:   {profiles_arr.shape} — {size_mb:.0f} MB")
    print(f"  nrel_conditions.npy: {conditions_arr.shape}")
    print(f"  Annual kWh mean:     {meta['annual_kwh_mean']:,.0f}")


if __name__ == "__main__":
    main()
