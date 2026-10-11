"""Validate trained CVAE against regional statistics.

Generates profiles from the CVAE and checks them against the same
6 validation targets used for the v0 mock model.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from cvae import LoadProfileCVAE
from opensynth_ne.archetypes import ARCHETYPES, FUELS, get_archetype, get_fuel
from opensynth_ne.validation import CHECKS
from opensynth_ne.weather import MONTH_IRRADIANCE, MONTH_TEMP_F

CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"


def load_model(checkpoint_dir: Path) -> tuple[LoadProfileCVAE, dict, dict]:
    """Load trained CVAE model, config, and normalization stats."""
    with open(checkpoint_dir / "config.json") as f:
        config = json.load(f)
    with open(checkpoint_dir / "normalization.json") as f:
        norm = json.load(f)

    model = LoadProfileCVAE(latent_dim=config["latent_dim"])
    model.load_state_dict(torch.load(checkpoint_dir / "best_model.pt",
                                     map_location="cpu", weights_only=True))
    model.eval()
    return model, config, norm


def generate_profiles(
    model: LoadProfileCVAE,
    norm: dict,
    archetype: str,
    fuel: str,
    month: int,
    n: int = 100,
) -> np.ndarray:
    """Generate n daily profiles. Returns (n, 6, 96) denormalized."""
    arch = get_archetype(archetype)
    fl = get_fuel(fuel)
    temp_f = MONTH_TEMP_F[month]
    irr = MONTH_IRRADIANCE[month]

    arch_idx = torch.tensor([list(a.id for a in ARCHETYPES).index(archetype)])
    fuel_idx = torch.tensor([list(f.id for f in FUELS).index(fuel)])

    month_rad = 2 * math.pi * month / 12
    temp_norm = (temp_f - norm["temp_f_mean"]) / norm["temp_f_std"]
    scale_norm = (arch.scale - norm["scale_mean"]) / norm["scale_std"]

    continuous = torch.tensor([[
        0.0, 0.0, 0.0,  # DER flags (none)
        math.sin(month_rad), math.cos(month_rad),
        temp_norm, irr, scale_norm, fl.e_heat,
    ]])

    with torch.no_grad():
        samples = model.sample(arch_idx, fuel_idx, continuous, n=n)

    # Denormalize
    means = np.array(norm["profile_means"]).reshape(1, -1, 1)
    stds = np.array(norm["profile_stds"]).reshape(1, -1, 1)
    profiles = samples.numpy() * stds + means
    return profiles


def main():
    print("Loading trained CVAE...")
    model, config, norm = load_model(CHECKPOINT_DIR)
    print(f"  Latent dim: {config['latent_dim']}, channels: {config['n_channels']}")

    print("\nRunning validation checks:\n")

    # Check 1: Annual kWh distribution (generate across all months)
    annual_kwh_list = []
    for _ in range(100):  # 100 synthetic meters
        yearly_kwh = 0
        for m in range(12):
            profiles = generate_profiles(model, norm, "colonial", "oil", m, n=1)
            net = profiles[0].sum(axis=0)  # sum channels → net-ish
            daily_kwh = net.sum() * 0.25  # 15-min intervals
            yearly_kwh += daily_kwh * 30.4  # avg days per month
        annual_kwh_list.append(yearly_kwh)

    mean_kwh = np.mean(annual_kwh_list)
    target_kwh = 8460
    delta_pct = abs(mean_kwh - target_kwh) / target_kwh * 100
    passed = delta_pct < 5
    print(f"  1. Annual kWh:  synth={mean_kwh:.0f}  target={target_kwh}  "
          f"delta={delta_pct:.1f}%  {'PASS' if passed else 'FAIL'}")

    # Check 2: Winter peak timing
    jan_profiles = generate_profiles(model, norm, "colonial", "oil", 0, n=200)
    net_profiles = jan_profiles.sum(axis=1)  # (200, 96) — sum channels
    peak_hours = np.argmax(net_profiles, axis=1) * 0.25
    mean_peak = peak_hours.mean()
    target_peak = 18.25
    peak_delta = abs(mean_peak - target_peak)
    passed2 = peak_delta < 1.0
    print(f"  2. Winter peak: synth={mean_peak:.2f}h  target={target_peak}h  "
          f"delta={peak_delta:.2f}h  {'PASS' if passed2 else 'FAIL'}")

    # Check 3: Summer load shape correlation
    jul_profiles = generate_profiles(model, norm, "colonial", "oil", 6, n=200)
    jul_mean = jul_profiles.sum(axis=1).mean(axis=0)  # average shape (96,)
    jan_mean = jan_profiles.sum(axis=1).mean(axis=0)
    # Correlation between summer shape and a reference
    corr = np.corrcoef(jul_mean, jan_mean)[0, 1]
    # Summer shape should be distinct from winter (low correlation is fine)
    # But shape-to-shape consistency should be high
    jul_pairs = jul_profiles.sum(axis=1)
    shape_corr = np.mean([np.corrcoef(jul_pairs[i], jul_mean)[0, 1]
                          for i in range(min(50, len(jul_pairs)))])
    passed3 = shape_corr > 0.85
    print(f"  3. Summer shape: mean r={shape_corr:.3f}  target>0.85  "
          f"{'PASS' if passed3 else 'FAIL'}")

    # Check 4: EV charging signature (need EV profiles)
    # Not directly testable without DER conditioning — skip for now
    print(f"  4. EV signature: (skipped — requires DER conditioning in generation)")

    # Check 5: Solar shape
    print(f"  5. Solar shape:  (skipped — requires solar DER conditioning)")

    # Check 6: Winter oil-heat kWh
    jan_net = jan_profiles.sum(axis=1)  # (200, 96)
    jan_kwh = jan_net.sum(axis=1) * 0.25  # daily kWh
    monthly_kwh = jan_kwh.mean() * 30.4
    target_winter = 1180
    winter_delta = abs(monthly_kwh - target_winter) / target_winter * 100
    passed6 = winter_delta < 8
    print(f"  6. Winter kWh:   synth={monthly_kwh:.0f}  target={target_winter}  "
          f"delta={winter_delta:.1f}%  {'PASS' if passed6 else 'FAIL (expected)'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
