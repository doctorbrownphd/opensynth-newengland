"""Upload CVAE weights and static dataset to HuggingFace Hub.

Usage:
    python scripts/upload_huggingface.py --repo doctorbrownphd/opensynth-newengland

Requires: huggingface_hub (pip install huggingface_hub)
         Must be logged in: python -c "from huggingface_hub import login; login()"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import HfApi, create_repo


def main():
    parser = argparse.ArgumentParser(description="Upload to HuggingFace Hub")
    parser.add_argument("--repo", default="doctorbrownphd/opensynth-newengland",
                        help="HuggingFace repo ID")
    parser.add_argument("--weights-dir", type=Path,
                        default=Path(__file__).parent.parent / "src" / "opensynth_ne" / "weights")
    parser.add_argument("--dataset-dir", type=Path,
                        default=Path(__file__).parent.parent / "dataset")
    parser.add_argument("--skip-dataset", action="store_true",
                        help="Skip dataset upload (weights only)")
    args = parser.parse_args()

    api = HfApi()

    # --- Model repo ---
    model_repo = args.repo
    print(f"Creating/updating model repo: {model_repo}")
    create_repo(model_repo, repo_type="model", exist_ok=True)

    # Upload weights
    weight_files = ["best_model.pt", "config.json", "normalization.json"]
    for fname in weight_files:
        fpath = args.weights_dir / fname
        if fpath.exists():
            print(f"  Uploading {fname} ({fpath.stat().st_size:,} bytes)...")
            api.upload_file(
                path_or_fileobj=str(fpath),
                path_in_repo=fname,
                repo_id=model_repo,
                repo_type="model",
            )
        else:
            print(f"  SKIP {fname} (not found)")

    # Upload model card
    model_card = """---
language: en
license: apache-2.0
tags:
  - energy
  - synthetic-data
  - AMI
  - load-profiles
  - new-england
  - CVAE
library_name: pytorch
---

# OpenSynth New England — CVAE Weights

Conditional Variational Autoencoder for generating synthetic AMI load profiles
conditioned on New England housing archetypes, heating fuel, weather, and DER.

## Usage

```python
pip install opensynth-newengland[cvae]
# Download weights to src/opensynth_ne/weights/
from opensynth_ne import generate_day
df, summary = generate_day(archetype="colonial", fuel="oil", month=0)
```

## Architecture

- 948k parameters
- 6-channel output: base, behav, heat, cool, ev, solar (96 timesteps each)
- 32-dim latent space, 25-dim conditioning vector
- Trained with cyclical beta annealing + free bits (0.5 nats/dim)

## Training

- 500k synthetic profiles from v0 mock model
- 200 epochs, early stopped at 70
- Val reconstruction MSE: 0.2225

## Repository

https://github.com/doctorbrownphd/opensynth-newengland
"""
    api.upload_file(
        path_or_fileobj=model_card.encode(),
        path_in_repo="README.md",
        repo_id=model_repo,
        repo_type="model",
    )
    print(f"  Model repo ready: https://huggingface.co/{model_repo}")

    # --- Dataset repo ---
    if args.skip_dataset:
        print("\nSkipping dataset upload.")
        return

    if not args.dataset_dir.exists():
        print(f"\nDataset dir {args.dataset_dir} not found — skipping.")
        return

    dataset_repo = args.repo + "-dataset"
    print(f"\nCreating/updating dataset repo: {dataset_repo}")
    create_repo(dataset_repo, repo_type="dataset", exist_ok=True)

    # Upload all parquet files preserving Hive partition structure
    parquet_files = list(args.dataset_dir.rglob("*.parquet"))
    print(f"  Found {len(parquet_files)} parquet partitions")

    for pf in parquet_files:
        rel_path = pf.relative_to(args.dataset_dir)
        size_mb = pf.stat().st_size / 1e6
        print(f"  Uploading {rel_path} ({size_mb:.1f} MB)...")
        api.upload_file(
            path_or_fileobj=str(pf),
            path_in_repo=str(rel_path),
            repo_id=dataset_repo,
            repo_type="dataset",
        )

    # Dataset card
    dataset_card = """---
language: en
license: cc-by-4.0
tags:
  - energy
  - synthetic-data
  - AMI
  - load-profiles
  - new-england
size_categories:
  - 100M<n<1B
---

# OpenSynth New England — Static Dataset v1.0

10,000 synthetic residential smart meter profiles for New England,
15-minute intervals, full calendar year.

## Format

Hive-partitioned Parquet: `archetype=X/fuel=Y/der=Z/data.parquet`

## Schema

| Column | Type | Description |
|--------|------|-------------|
| meter_id | string | Unique meter identifier |
| day_of_year | int | 0-364 |
| month | int | 0-11 |
| interval | int | 0-95 (15-min intervals) |
| hour | float | 0.0-23.75 |
| net | float | Net load (kW) |
| gross | float | Gross load (kW) |
| base | float | Baseload component (kW) |
| heat | float | Heating component (kW) |
| ev | float | EV charging (kW) |
| cool | float | Cooling (kW) |
| solar | float | Solar generation (kW, negative) |
| behav | float | Behavioral load (kW) |

## Coverage

- 8 housing archetypes × 4 fuel types × 3 DER configs = 96 base types
- 10,000 meters with per-meter latent variation
- Geography: NH, MA, CT, RI, VT, ME

## Repository

https://github.com/doctorbrownphd/opensynth-newengland
"""
    api.upload_file(
        path_or_fileobj=dataset_card.encode(),
        path_in_repo="README.md",
        repo_id=dataset_repo,
        repo_type="dataset",
    )
    print(f"  Dataset repo ready: https://huggingface.co/datasets/{dataset_repo}")
    print("\nDone.")


if __name__ == "__main__":
    main()
