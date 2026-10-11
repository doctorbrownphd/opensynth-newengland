"""Conditional Variational Autoencoder for load profile generation.

6-channel output (base, behav, heat, cool, ev, solar) × 96 timesteps.
Conditioned on archetype, fuel, DER, month, temperature, irradiance.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class ConditionEncoder(nn.Module):
    """Encode conditioning variables into a fixed-size vector.

    Categorical: archetype (8→10), fuel (4→6), day_type (3→4)
    Continuous: DER flags (3) + month sin/cos (2) + temp + irr + scale + e_heat

    Output dimension: 29
    """

    COND_DIM = 29

    def __init__(self, n_archetypes: int = 8, n_fuels: int = 4, n_day_types: int = 3):
        super().__init__()
        self.arch_emb = nn.Embedding(n_archetypes, 10)
        self.fuel_emb = nn.Embedding(n_fuels, 6)
        self.day_type_emb = nn.Embedding(n_day_types, 4)

    def forward(
        self,
        arch_idx: torch.Tensor,      # (B,) long
        fuel_idx: torch.Tensor,      # (B,) long
        day_type_idx: torch.Tensor,  # (B,) long
        continuous: torch.Tensor,    # (B, 9) — der(3) + month_sc(2) + temp + irr + scale + e_heat
    ) -> torch.Tensor:
        """Returns (B, 29) conditioning vector."""
        a = self.arch_emb(arch_idx)           # (B, 10)
        f = self.fuel_emb(fuel_idx)           # (B, 6)
        d = self.day_type_emb(day_type_idx)   # (B, 4)
        return torch.cat([a, f, d, continuous], dim=-1)  # (B, 29)


class LoadProfileCVAE(nn.Module):
    """Conditional VAE for 6-channel × 96-timestep load profiles.

    Encoder: (profile_flat + condition) → (mu, logvar)
    Decoder: (z + condition) → reconstructed profile
    """

    def __init__(
        self,
        n_channels: int = 6,
        n_timesteps: int = 96,
        latent_dim: int = 32,
        cond_dim: int = ConditionEncoder.COND_DIM,
    ):
        super().__init__()
        self.n_channels = n_channels
        self.n_timesteps = n_timesteps
        self.latent_dim = latent_dim
        self.cond_dim = cond_dim
        self.profile_flat = n_channels * n_timesteps  # 576

        self.condition_encoder = ConditionEncoder()

        # Encoder: (576 + 25) = 601 → latent
        enc_in = self.profile_flat + cond_dim
        self.encoder = nn.Sequential(
            nn.Linear(enc_in, 512),
            nn.ReLU(),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
        )
        self.mu_head = nn.Linear(128, latent_dim)
        self.logvar_head = nn.Linear(128, latent_dim)

        # Decoder: (32 + 25) = 57 → profile
        dec_in = latent_dim + cond_dim
        self.decoder = nn.Sequential(
            nn.Linear(dec_in, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, 512),
            nn.ReLU(),
            nn.Linear(512, self.profile_flat),
        )

    def encode(self, x: torch.Tensor, c: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode profile + condition → (mu, logvar)."""
        x_flat = x.view(x.size(0), -1)  # (B, 576)
        h = self.encoder(torch.cat([x_flat, c], dim=-1))
        return self.mu_head(h), self.logvar_head(h)

    def reparameterize(self, mu: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        """Sample z ~ N(mu, sigma^2) using the reparameterization trick."""
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z: torch.Tensor, c: torch.Tensor) -> torch.Tensor:
        """Decode latent + condition → profile (B, 6, 96)."""
        h = self.decoder(torch.cat([z, c], dim=-1))
        x = h.view(-1, self.n_channels, self.n_timesteps)

        # Per-channel activations:
        # Channels 0-4 (base, behav, heat, cool, ev): softplus (non-negative)
        # Channel 5 (solar): negative softplus (non-positive generation)
        pos = F.softplus(x[:, :5, :])
        neg = -F.softplus(x[:, 5:6, :])
        return torch.cat([pos, neg], dim=1)

    def forward(
        self,
        x: torch.Tensor,              # (B, 6, 96)
        arch_idx: torch.Tensor,       # (B,) long
        fuel_idx: torch.Tensor,       # (B,) long
        day_type_idx: torch.Tensor,   # (B,) long
        continuous: torch.Tensor,     # (B, 9)
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Full forward pass. Returns (x_recon, mu, logvar)."""
        c = self.condition_encoder(arch_idx, fuel_idx, day_type_idx, continuous)
        mu, logvar = self.encode(x, c)
        z = self.reparameterize(mu, logvar)
        x_recon = self.decode(z, c)
        return x_recon, mu, logvar

    def sample(
        self,
        arch_idx: torch.Tensor,
        fuel_idx: torch.Tensor,
        day_type_idx: torch.Tensor,
        continuous: torch.Tensor,
        n: int = 1,
    ) -> torch.Tensor:
        """Sample from the prior. Returns (n, 6, 96)."""
        c = self.condition_encoder(arch_idx, fuel_idx, day_type_idx, continuous)
        if c.size(0) == 1 and n > 1:
            c = c.expand(n, -1)
        z = torch.randn(c.size(0), self.latent_dim, device=c.device)
        return self.decode(z, c)


def _free_bits_kl(mu: torch.Tensor, logvar: torch.Tensor, free_bits: float = 0.5) -> torch.Tensor:
    """KL divergence with free bits — prevents posterior collapse.

    Applies a per-dimension minimum: each latent dimension must contribute
    at least `free_bits` nats of KL before the loss kicks in. This stops
    the encoder from learning to ignore the latent space entirely.
    """
    # Per-dimension KL: (B, D)
    kl_per_dim = -0.5 * (1 + logvar - mu.pow(2) - logvar.exp())
    # Average across batch, then apply free bits floor per dimension
    kl_mean = kl_per_dim.mean(dim=0)  # (D,)
    kl_clamped = torch.clamp(kl_mean, min=free_bits)
    return kl_clamped.sum()


def cyclical_beta(epoch: int, cycle_length: int = 40, ratio: float = 0.5) -> float:
    """Cyclical annealing schedule for beta.

    Each cycle: linearly ramp from 0 to 1 over the first `ratio` fraction,
    then hold at 1 for the remainder. Repeats every `cycle_length` epochs.
    This forces the model to repeatedly re-engage the latent space.
    """
    pos_in_cycle = epoch % cycle_length
    ramp_length = int(cycle_length * ratio)
    if pos_in_cycle < ramp_length:
        return pos_in_cycle / ramp_length
    return 1.0


def cvae_loss(
    x: torch.Tensor,
    x_recon: torch.Tensor,
    mu: torch.Tensor,
    logvar: torch.Tensor,
    beta: float = 1.0,
    lambda_smooth: float = 0.1,
    free_bits: float = 0.5,
) -> tuple[torch.Tensor, dict]:
    """CVAE loss: reconstruction + KL (free bits) + smoothness + solar sign penalty.

    Returns (total_loss, components_dict).
    """
    # Reconstruction: MSE
    recon = F.mse_loss(x_recon, x, reduction="mean")

    # KL divergence with free bits
    kl = _free_bits_kl(mu, logvar, free_bits=free_bits)

    # Raw KL for logging (without free bits)
    kl_raw = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())

    # Smoothness: penalize large jumps between adjacent timesteps
    diff = x_recon[:, :, 1:] - x_recon[:, :, :-1]
    smooth = torch.mean(diff.pow(2))

    # Solar sign penalty: channel 5 should be <= 0
    solar_penalty = torch.mean(F.relu(x_recon[:, 5, :]))

    total = recon + beta * kl + lambda_smooth * smooth + 10.0 * solar_penalty

    return total, {
        "total": total.item(),
        "recon": recon.item(),
        "kl": kl.item(),
        "kl_raw": kl_raw.item(),
        "smooth": smooth.item(),
        "solar_penalty": solar_penalty.item(),
    }
