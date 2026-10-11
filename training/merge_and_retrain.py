"""Merge NREL real data with mock synthetic data for CVAE training.

Real data provides distribution calibration — the CVAE learns the
statistical shape of real NE load profiles while the mock data
provides conditioning coverage across all 96 base types.

Usage:
    python training/fetch_nrel.py --per-state 50   # download first
    python training/merge_and_retrain.py            # merge + retrain
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

MOCK_DIR = Path(__file__).parent / "data"
NREL_DIR = Path(__file__).parent / "reference_data" / "nrel"
OUTPUT_DIR = Path(__file__).parent / "data_merged"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load mock data
    print("Loading mock data...")
    mock_profiles = np.load(MOCK_DIR / "profiles.npy")
    mock_conditions = np.load(MOCK_DIR / "conditions.npy")
    with open(MOCK_DIR / "meta.json") as f:
        mock_meta = json.load(f)
    print(f"  Mock: {mock_profiles.shape[0]:,} profiles")

    # Load NREL data
    print("Loading NREL data...")
    nrel_profiles = np.load(NREL_DIR / "nrel_profiles.npy")
    nrel_conditions = np.load(NREL_DIR / "nrel_conditions.npy")
    with open(NREL_DIR / "nrel_meta.json") as f:
        nrel_meta = json.load(f)
    print(f"  NREL: {nrel_profiles.shape[0]:,} profiles")

    # Merge — oversample NREL to ~30% of total for distribution influence
    n_mock = mock_profiles.shape[0]
    n_nrel = nrel_profiles.shape[0]
    target_nrel_frac = 0.30
    n_nrel_target = int(n_mock * target_nrel_frac / (1 - target_nrel_frac))

    if n_nrel < n_nrel_target:
        # Oversample NREL with replacement
        rng = np.random.default_rng(42)
        oversample_idx = rng.choice(n_nrel, size=n_nrel_target, replace=True)
        nrel_profiles_resampled = nrel_profiles[oversample_idx]
        nrel_conditions_resampled = nrel_conditions[oversample_idx]
        print(f"  Oversampled NREL: {n_nrel} → {n_nrel_target}")
    else:
        nrel_profiles_resampled = nrel_profiles[:n_nrel_target]
        nrel_conditions_resampled = nrel_conditions[:n_nrel_target]

    # Concatenate
    merged_profiles = np.concatenate([mock_profiles, nrel_profiles_resampled], axis=0)
    merged_conditions = np.concatenate([mock_conditions, nrel_conditions_resampled], axis=0)

    # Shuffle
    rng = np.random.default_rng(42)
    shuffle_idx = rng.permutation(len(merged_profiles))
    merged_profiles = merged_profiles[shuffle_idx]
    merged_conditions = merged_conditions[shuffle_idx]

    print(f"\n  Merged: {merged_profiles.shape[0]:,} profiles "
          f"({n_mock:,} mock + {len(nrel_profiles_resampled):,} NREL)")
    nrel_frac = len(nrel_profiles_resampled) / len(merged_profiles)
    print(f"  NREL fraction: {nrel_frac:.1%}")

    # Recompute normalization stats on merged data
    profile_means = merged_profiles.mean(axis=(0, 2))
    profile_stds = merged_profiles.std(axis=(0, 2))
    temp_vals = merged_conditions[:, 7]
    scale_vals = merged_conditions[:, 9]

    meta = {
        **mock_meta,
        "n_samples": int(len(merged_profiles)),
        "n_mock": n_mock,
        "n_nrel": int(len(nrel_profiles_resampled)),
        "nrel_fraction": round(nrel_frac, 3),
        "nrel_source": nrel_meta.get("source", "NREL ResStock"),
        "nrel_states": nrel_meta.get("states", []),
        "profile_means": profile_means.tolist(),
        "profile_stds": profile_stds.tolist(),
        "temp_f_mean": float(temp_vals.mean()),
        "temp_f_std": float(temp_vals.std()),
        "scale_mean": float(scale_vals.mean()),
        "scale_std": float(scale_vals.std()),
    }

    # Save
    np.save(OUTPUT_DIR / "profiles.npy", merged_profiles)
    np.save(OUTPUT_DIR / "conditions.npy", merged_conditions)
    with open(OUTPUT_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    size_mb = (OUTPUT_DIR / "profiles.npy").stat().st_size / 1e6
    print(f"\n  Saved to {OUTPUT_DIR}/")
    print(f"  profiles.npy:   {merged_profiles.shape} — {size_mb:.0f} MB")
    print(f"  conditions.npy: {merged_conditions.shape}")

    print(f"\nTo retrain with merged data:")
    print(f"  python training/train.py --data-dir training/data_merged --epochs 200")


if __name__ == "__main__":
    main()
