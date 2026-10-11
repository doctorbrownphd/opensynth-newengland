"""CVAE inference — loads trained weights and generates load profiles.

This module is lazily imported only when CVAE weights are detected.
It requires torch as a dependency (pip install opensynth-newengland[cvae]).
"""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path
from typing import ClassVar

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from opensynth_ne.archetypes import ARCHETYPES, FUELS, get_archetype, get_fuel
from opensynth_ne.weather import MONTH_IRRADIANCE, MONTH_TEMP_F

WEIGHTS_DIR = Path(__file__).parent / "weights"

# --- Inline model definition (matches training/cvae.py) ---
# Duplicated here to avoid importing from training/ at runtime.


class _ConditionEncoder(nn.Module):
    COND_DIM = 29

    def __init__(self):
        super().__init__()
        self.arch_emb = nn.Embedding(8, 10)
        self.fuel_emb = nn.Embedding(4, 6)
        self.day_type_emb = nn.Embedding(3, 4)

    def forward(self, arch_idx, fuel_idx, day_type_idx, continuous):
        a = self.arch_emb(arch_idx)
        f = self.fuel_emb(fuel_idx)
        d = self.day_type_emb(day_type_idx)
        return torch.cat([a, f, d, continuous], dim=-1)


class _LoadProfileCVAE(nn.Module):
    def __init__(self, latent_dim=32, n_channels=6, n_timesteps=96, cond_dim=29):
        super().__init__()
        self.n_channels = n_channels
        self.n_timesteps = n_timesteps
        self.latent_dim = latent_dim
        self.cond_dim = cond_dim
        self.profile_flat = n_channels * n_timesteps

        self.condition_encoder = _ConditionEncoder()

        enc_in = self.profile_flat + cond_dim
        self.encoder = nn.Sequential(
            nn.Linear(enc_in, 512), nn.ReLU(),
            nn.Linear(512, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(),
        )
        self.mu_head = nn.Linear(128, latent_dim)
        self.logvar_head = nn.Linear(128, latent_dim)

        dec_in = latent_dim + cond_dim
        self.decoder = nn.Sequential(
            nn.Linear(dec_in, 128), nn.ReLU(),
            nn.Linear(128, 256), nn.ReLU(),
            nn.Linear(256, 512), nn.ReLU(),
            nn.Linear(512, self.profile_flat),
        )

    def decode(self, z, c):
        h = self.decoder(torch.cat([z, c], dim=-1))
        x = h.view(-1, self.n_channels, self.n_timesteps)
        pos = F.softplus(x[:, :5, :])
        neg = -F.softplus(x[:, 5:6, :])
        return torch.cat([pos, neg], dim=1)

    def sample(self, arch_idx, fuel_idx, continuous, n=1):
        c = self.condition_encoder(arch_idx, fuel_idx, continuous)
        if c.size(0) == 1 and n > 1:
            c = c.expand(n, -1)
        z = torch.randn(c.size(0), self.latent_dim)
        return self.decode(z, c)


# --- Index mappings ---
_ARCH_IDS = [a.id for a in ARCHETYPES]
_FUEL_IDS = [f.id for f in FUELS]


class CVAEGenerator:
    """Loads a trained CVAE and generates load profiles.

    Singleton pattern — model loads once (~50ms), subsequent calls <1ms.
    Thread-safe via double-checked locking.
    """

    _instance: CVAEGenerator | None = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, weights_dir: Path | None = None):
        wdir = weights_dir or WEIGHTS_DIR

        required = ["config.json", "normalization.json", "best_model.pt"]
        for fname in required:
            if not (wdir / fname).exists():
                raise FileNotFoundError(
                    f"Missing {fname} in {wdir}. "
                    "Download weights from HuggingFace or run training/export_model.py"
                )

        with open(wdir / "config.json") as f:
            self.config = json.load(f)
        with open(wdir / "normalization.json") as f:
            self.norm = json.load(f)

        self.model = _LoadProfileCVAE(latent_dim=self.config["latent_dim"])
        self.model.load_state_dict(
            torch.load(wdir / "best_model.pt", map_location="cpu", weights_only=True)
        )
        self.model.eval()

        self._profile_means = np.array(self.norm["profile_means"]).reshape(1, -1, 1)
        self._profile_stds = np.array(self.norm["profile_stds"]).reshape(1, -1, 1)

    @classmethod
    def get(cls) -> CVAEGenerator:
        """Thread-safe singleton accessor (double-checked locking)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def is_available(cls) -> bool:
        """Check if weights exist on disk."""
        return (WEIGHTS_DIR / "best_model.pt").exists()

    _DAY_TYPE_TO_IDX = {"weekday": 0, "weekend": 1, "holiday": 2}

    def generate_day(
        self,
        archetype: str = "colonial",
        fuel: str = "oil",
        month: int = 0,
        temp_f: float | None = None,
        has_ev: bool = False,
        has_solar: bool = False,
        has_battery: bool = False,
        day_type: str = "weekday",
        seed: int = 42,
    ) -> np.ndarray:
        """Generate one day profile. Returns (6, 96) numpy array.

        Channels: base, behav, heat, cool, ev, solar.
        """
        arch = get_archetype(archetype)
        fl = get_fuel(fuel)
        temp = MONTH_TEMP_F[month] if temp_f is None else temp_f

        arch_idx = torch.tensor([_ARCH_IDS.index(archetype)])
        fuel_idx = torch.tensor([_FUEL_IDS.index(fuel)])
        dt_idx = torch.tensor([self._DAY_TYPE_TO_IDX.get(day_type, 0)])

        month_rad = 2 * math.pi * month / 12
        temp_norm = (temp - self.norm["temp_f_mean"]) / self.norm["temp_f_std"]
        scale_norm = (arch.scale - self.norm["scale_mean"]) / self.norm["scale_std"]

        continuous = torch.tensor([[
            float(has_ev), float(has_solar), float(has_battery),
            math.sin(month_rad), math.cos(month_rad),
            temp_norm, MONTH_IRRADIANCE[month], scale_norm, fl.e_heat,
        ]])

        gen = torch.Generator().manual_seed(seed)
        with torch.no_grad():
            c = self.model.condition_encoder(arch_idx, fuel_idx, dt_idx, continuous)
            z = torch.randn(1, self.model.latent_dim, generator=gen)
            profile = self.model.decode(z, c)

        result = profile.numpy() * self._profile_stds + self._profile_means
        return result[0]
