"""Export the v1.0 static dataset: 10,000 synthetic meters, full year.

Produces Hive-partitioned Parquet files:
    dataset/archetype=colonial/fuel=oil/der=none/data.parquet
    dataset/archetype=colonial/fuel=oil/der=solar/data.parquet
    ...

Also produces a single CSV for portability.

Usage:
    python scripts/export_dataset.py                      # full 10k (slow)
    python scripts/export_dataset.py --n 100 --out test   # quick test
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from opensynth_ne.archetypes import ARCHETYPES, DER_CONFIGS, FUELS
from opensynth_ne.model import generate, _build_catalog_weights, _mulberry32, _hash_str


def allocate_meters(n: int, seed: int = 42) -> list[dict]:
    """Distribute n meters across 96 base types using empirical weights."""
    catalog = _build_catalog_weights(seed)
    weights = [entry[6] for entry in catalog]

    # Proportional allocation with rounding
    total_w = sum(weights)
    raw_alloc = [w / total_w * n for w in weights]

    # Round down, then distribute remainder by largest fractional part
    alloc = [int(a) for a in raw_alloc]
    remainder = n - sum(alloc)
    fracs = [(raw_alloc[i] - alloc[i], i) for i in range(len(alloc))]
    fracs.sort(reverse=True)
    for i in range(remainder):
        alloc[fracs[i][1]] += 1

    result = []
    for i, entry in enumerate(catalog):
        if alloc[i] > 0:
            result.append({
                "archetype": entry[0],
                "fuel": entry[1],
                "der": entry[2],
                "ev": entry[3],
                "solar": entry[4],
                "battery": entry[5],
                "count": alloc[i],
            })
    return result


def main():
    parser = argparse.ArgumentParser(description="Export static dataset")
    parser.add_argument("--n", type=int, default=10000, help="Number of meters")
    parser.add_argument("--out", type=str, default="dataset", help="Output directory name")
    parser.add_argument("--csv", action="store_true", help="Also export single CSV")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_dir = Path(__file__).parent.parent / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Exporting {args.n:,} meters to {out_dir}/")
    print(f"  Format: Hive-partitioned Parquet")
    if args.csv:
        print(f"  + single CSV")

    # Allocate meters
    allocations = allocate_meters(args.n, args.seed)
    total_meters = sum(a["count"] for a in allocations)
    print(f"  {len(allocations)} base types, {total_meters:,} meters total")

    t0 = time.time()
    meter_offset = 0
    all_csv_frames = [] if args.csv else None

    for alloc_i, alloc in enumerate(allocations):
        n_meters = alloc["count"]
        if n_meters == 0:
            continue

        print(f"  [{alloc_i+1}/{len(allocations)}] {alloc['archetype']}/{alloc['fuel']}/{alloc['der']} "
              f"— {n_meters} meters...", end="", flush=True)

        t1 = time.time()

        # Generate full year for this base type
        df = generate(
            n=n_meters,
            archetype=alloc["archetype"],
            fuel=alloc["fuel"],
            month=None,  # full year
            has_ev=alloc["ev"],
            has_solar=alloc["solar"],
            has_battery=alloc["battery"],
            seed=args.seed + meter_offset,
        )

        # Remap meter IDs to global namespace
        local_ids = sorted(df["meter_id"].unique())
        id_map = {old: f"meter_{meter_offset + i:05d}" for i, old in enumerate(local_ids)}
        df["meter_id"] = df["meter_id"].map(id_map)

        # Write Hive-partitioned parquet
        partition_dir = (out_dir / f"archetype={alloc['archetype']}" /
                         f"fuel={alloc['fuel']}" / f"der={alloc['der']}")
        partition_dir.mkdir(parents=True, exist_ok=True)

        # Drop partition columns from the data file (they're in the path)
        write_df = df.drop(columns=["archetype", "fuel", "der"])
        write_df.to_parquet(partition_dir / "data.parquet", index=False, engine="pyarrow")

        if all_csv_frames is not None:
            all_csv_frames.append(df)

        elapsed = time.time() - t1
        rows = len(df)
        print(f" {rows:,} rows in {elapsed:.1f}s")

        meter_offset += n_meters

    total_time = time.time() - t0
    print(f"\nDone in {total_time:.0f}s")

    # Write CSV
    if all_csv_frames:
        csv_path = out_dir / "opensynth-ne-v1.0.csv"
        print(f"Writing CSV to {csv_path}...", end="", flush=True)
        full_df = pd.concat(all_csv_frames, ignore_index=True)
        full_df.to_csv(csv_path, index=False)
        csv_size = csv_path.stat().st_size / 1e9
        print(f" {csv_size:.2f} GB")

    # Summary
    parquet_size = sum(f.stat().st_size for f in out_dir.rglob("*.parquet")) / 1e9
    n_partitions = sum(1 for _ in out_dir.rglob("*.parquet"))
    print(f"\nDataset summary:")
    print(f"  Meters:     {total_meters:,}")
    print(f"  Partitions: {n_partitions}")
    print(f"  Parquet:    {parquet_size:.2f} GB")


if __name__ == "__main__":
    main()
