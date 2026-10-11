"""Train the LoadProfileCVAE on synthetic data from the mock model.

Usage:
    python training/train.py --epochs 200
    python training/train.py --epochs 5 --batch-size 256  # quick smoke test
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from cvae import LoadProfileCVAE, cvae_loss, cyclical_beta

DATA_DIR = Path(__file__).parent / "data"
CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"


def load_data(data_dir: Path) -> tuple[np.ndarray, np.ndarray, dict]:
    """Load training data arrays and metadata."""
    profiles = np.load(data_dir / "profiles.npy")
    conditions = np.load(data_dir / "conditions.npy")
    with open(data_dir / "meta.json") as f:
        meta = json.load(f)
    return profiles, conditions, meta


def normalize_profiles(profiles: np.ndarray, meta: dict) -> np.ndarray:
    """Z-score normalize each channel using training set statistics."""
    means = np.array(meta["profile_means"]).reshape(1, -1, 1)
    stds = np.array(meta["profile_stds"]).reshape(1, -1, 1)
    stds = np.where(stds < 1e-6, 1.0, stds)  # avoid div by zero
    return ((profiles - means) / stds).astype(np.float32)


def normalize_conditions(conditions: np.ndarray, meta: dict) -> np.ndarray:
    """Normalize continuous condition columns (temp_f, scale)."""
    cond = conditions.copy()
    # Column 7: temp_f → z-score
    cond[:, 7] = (cond[:, 7] - meta["temp_f_mean"]) / meta["temp_f_std"]
    # Column 9: scale → z-score
    cond[:, 9] = (cond[:, 9] - meta["scale_mean"]) / meta["scale_std"]
    return cond.astype(np.float32)


def make_dataloaders(
    profiles: np.ndarray,
    conditions: np.ndarray,
    batch_size: int,
    val_frac: float = 0.1,
    seed: int = 42,
) -> tuple[DataLoader, DataLoader]:
    """Split data and create train/val DataLoaders."""
    n = len(profiles)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    val_n = int(n * val_frac)

    val_idx, train_idx = idx[:val_n], idx[val_n:]

    def make_loader(subset_idx, shuffle):
        p = torch.from_numpy(profiles[subset_idx])
        c = torch.from_numpy(conditions[subset_idx])
        arch = c[:, 0].long()
        fuel = c[:, 1].long()
        day_type = c[:, 11].long()  # day_type_idx is the last condition column
        cont = c[:, 2:11]  # 9 continuous/boolean features (skip day_type_idx)
        ds = TensorDataset(p, arch, fuel, day_type, cont)
        return DataLoader(ds, batch_size=batch_size, shuffle=shuffle,
                          num_workers=0, pin_memory=True)

    return make_loader(train_idx, True), make_loader(val_idx, False)


def train_epoch(
    model: LoadProfileCVAE,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    beta: float,
    device: torch.device,
) -> dict:
    """Train one epoch. Returns average loss components."""
    model.train()
    totals = {"total": 0, "recon": 0, "kl": 0, "kl_raw": 0}
    n_batches = 0

    for x, arch, fuel, day_type, cont in loader:
        x = x.to(device)
        arch = arch.to(device)
        fuel = fuel.to(device)
        day_type = day_type.to(device)
        cont = cont.to(device)

        x_recon, mu, logvar = model(x, arch, fuel, day_type, cont)
        loss, parts = cvae_loss(x, x_recon, mu, logvar, beta=beta)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()

        for k in totals:
            totals[k] += parts[k]
        n_batches += 1

    return {k: v / n_batches for k, v in totals.items()}


@torch.no_grad()
def val_epoch(
    model: LoadProfileCVAE,
    loader: DataLoader,
    beta: float,
    device: torch.device,
) -> dict:
    """Validate one epoch. Returns average loss components."""
    model.eval()
    totals = {"total": 0, "recon": 0, "kl": 0, "kl_raw": 0}
    n_batches = 0

    for x, arch, fuel, day_type, cont in loader:
        x = x.to(device)
        arch = arch.to(device)
        fuel = fuel.to(device)
        day_type = day_type.to(device)
        cont = cont.to(device)

        x_recon, mu, logvar = model(x, arch, fuel, day_type, cont)
        _, parts = cvae_loss(x, x_recon, mu, logvar, beta=beta)

        for k in totals:
            totals[k] += parts[k]
        n_batches += 1

    return {k: v / n_batches for k, v in totals.items()}


def main():
    parser = argparse.ArgumentParser(description="Train LoadProfileCVAE")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=CHECKPOINT_DIR)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--latent-dim", type=int, default=32)
    parser.add_argument("--beta-cycle", type=int, default=40,
                        help="Cyclical annealing cycle length in epochs")
    parser.add_argument("--free-bits", type=float, default=0.5,
                        help="Minimum KL per latent dimension (nats)")
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed)
    device = torch.device("mps" if torch.backends.mps.is_available()
                          else "cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load and prepare data
    print("Loading data...")
    profiles, conditions, meta = load_data(args.data_dir)
    profiles_norm = normalize_profiles(profiles, meta)
    conditions_norm = normalize_conditions(conditions, meta)
    print(f"  {profiles.shape[0]:,} profiles, {profiles.shape[1]} channels, "
          f"{profiles.shape[2]} timesteps")

    train_loader, val_loader = make_dataloaders(
        profiles_norm, conditions_norm, args.batch_size, seed=args.seed
    )
    print(f"  Train: {len(train_loader.dataset):,}  Val: {len(val_loader.dataset):,}")

    # Build model
    model = LoadProfileCVAE(latent_dim=args.latent_dim).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Model: {n_params:,} parameters")

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    # Training loop
    best_val_loss = float("inf")
    patience_counter = 0
    log: list[dict] = []

    print(f"\nTraining for up to {args.epochs} epochs (patience={args.patience})...\n")

    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        beta = cyclical_beta(epoch, cycle_length=args.beta_cycle)

        train_metrics = train_epoch(model, train_loader, optimizer, beta, device)
        val_metrics = val_epoch(model, val_loader, beta, device)
        scheduler.step()

        elapsed = time.time() - t0
        lr = optimizer.param_groups[0]["lr"]

        entry = {
            "epoch": epoch, "beta": round(beta, 3), "lr": round(lr, 6),
            "train_loss": round(train_metrics["total"], 5),
            "train_recon": round(train_metrics["recon"], 5),
            "train_kl": round(train_metrics["kl"], 5),
            "train_kl_raw": round(train_metrics["kl_raw"], 5),
            "val_loss": round(val_metrics["total"], 5),
            "val_recon": round(val_metrics["recon"], 5),
            "val_kl": round(val_metrics["kl"], 5),
            "val_kl_raw": round(val_metrics["kl_raw"], 5),
            "time_s": round(elapsed, 1),
        }
        log.append(entry)

        # Checkpoint best — use recon loss only (not total with cyclical beta noise)
        improved = ""
        if val_metrics["recon"] < best_val_loss:
            best_val_loss = val_metrics["recon"]
            patience_counter = 0
            torch.save(model.state_dict(), args.out_dir / "best_model.pt")
            improved = " ★"
        else:
            patience_counter += 1

        if epoch <= 5 or epoch % 5 == 0 or improved:
            print(f"  [{epoch:3d}/{args.epochs}] β={beta:.2f}  "
                  f"train={train_metrics['total']:.4f} (r={train_metrics['recon']:.4f} "
                  f"kl={train_metrics['kl_raw']:.4f})  "
                  f"val_r={val_metrics['recon']:.4f} kl={val_metrics['kl_raw']:.4f}  "
                  f"lr={lr:.5f}  {elapsed:.1f}s{improved}")

        # Early stopping
        if patience_counter >= args.patience:
            print(f"\n  Early stopping at epoch {epoch} (no improvement for {args.patience} epochs)")
            break

    # Save config and log
    config = {
        "latent_dim": args.latent_dim,
        "n_channels": 6,
        "n_timesteps": 96,
        "cond_dim": model.cond_dim,
        "component_names": meta["component_names"],
    }
    with open(args.out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    normalization = {
        "temp_f_mean": meta["temp_f_mean"],
        "temp_f_std": meta["temp_f_std"],
        "scale_mean": meta["scale_mean"],
        "scale_std": meta["scale_std"],
        "profile_means": meta["profile_means"],
        "profile_stds": meta["profile_stds"],
    }
    with open(args.out_dir / "normalization.json", "w") as f:
        json.dump(normalization, f, indent=2)

    with open(args.out_dir / "train_log.json", "w") as f:
        json.dump(log, f, indent=2)

    print(f"\nBest val loss: {best_val_loss:.5f}")
    print(f"Saved to {args.out_dir}/")


if __name__ == "__main__":
    main()
