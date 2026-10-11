"""Integration tests for CVAE backend.

These tests only run when trained weights are installed at
src/opensynth_ne/weights/best_model.pt.
"""

from __future__ import annotations

import pathlib

import pytest

WEIGHTS_DIR = pathlib.Path(__file__).parent.parent / "src" / "opensynth_ne" / "weights"
WEIGHTS_EXIST = (WEIGHTS_DIR / "best_model.pt").exists()

pytestmark = pytest.mark.skipif(not WEIGHTS_EXIST, reason="CVAE weights not installed")


def _gen(**kwargs):
    from opensynth_ne.model import generate_day
    return generate_day(use_cvae=True, **kwargs)


class TestCVAEShape:
    def test_row_count(self):
        df, _ = _gen()
        assert len(df) == 96

    def test_columns(self):
        df, _ = _gen()
        expected = {"interval", "hour", "net", "gross", "base", "heat", "ev", "cool", "solar", "behav"}
        assert set(df.columns) == expected

    def test_summary_keys(self):
        _, s = _gen()
        assert set(s.keys()) == {"temp", "irr", "peak", "peak_hour", "min", "kwh"}


class TestCVAEDeterminism:
    def test_same_seed_same_output(self):
        df1, _ = _gen(seed=42)
        df2, _ = _gen(seed=42)
        assert df1.equals(df2)

    def test_different_seed_different_output(self):
        df1, _ = _gen(seed=42)
        df2, _ = _gen(seed=99)
        assert not df1["net"].equals(df2["net"])


class TestCVAEConstraints:
    def test_solar_zero_when_off(self):
        df, _ = _gen(has_solar=False)
        assert (df["solar"] == 0.0).all()

    def test_ev_zero_when_off(self):
        df, _ = _gen(has_ev=False)
        assert (df["ev"] == 0.0).all()

    def test_gross_positive(self):
        df, _ = _gen()
        assert (df["gross"] >= 0.05).all()

    def test_net_leq_gross(self):
        df, _ = _gen(has_solar=True, has_battery=True, month=6)
        assert (df["net"] <= df["gross"] + 0.001).all()


class TestCVAEPlausibility:
    def test_daily_kwh_reasonable(self):
        _, s = _gen(archetype="colonial", fuel="oil", month=0)
        assert 5 < s["kwh"] < 80

    def test_mock_cvae_distribution_overlap(self):
        """CVAE daily kWh should be within 30% of mock for same conditions."""
        from opensynth_ne.model import generate_day
        _, s_mock = generate_day(use_cvae=False, archetype="colonial", fuel="oil", month=0, seed=42)
        _, s_cvae = generate_day(use_cvae=True, archetype="colonial", fuel="oil", month=0, seed=42)
        assert abs(s_cvae["kwh"] - s_mock["kwh"]) / s_mock["kwh"] < 0.30
