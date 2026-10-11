"""Tests for generate() — batch multi-meter load profile generation."""

import pytest

from opensynth_ne.model import generate


class TestShape:
    """DataFrame shape and column correctness."""

    def test_single_month_shape(self):
        df = generate(n=5, month=0)
        assert len(df) == 5 * 96
        assert df["meter_id"].nunique() == 5

    def test_columns(self):
        df = generate(n=2, month=0)
        expected = {
            "meter_id", "archetype", "fuel", "der",
            "day_of_year", "month", "interval", "hour",
            "net", "gross", "base", "heat", "ev", "cool", "solar", "behav",
        }
        assert set(df.columns) == expected

    def test_n_equals_one(self):
        df = generate(n=1, month=0)
        assert len(df) == 96
        assert df["meter_id"].nunique() == 1

    def test_full_year_shape(self):
        """Full year: n meters x 365 days x 96 intervals."""
        df = generate(n=2, month=None)
        assert len(df) == 2 * 365 * 96
        assert df["meter_id"].nunique() == 2

    def test_meter_id_format(self):
        df = generate(n=3, month=0)
        ids = sorted(df["meter_id"].unique())
        assert ids == ["meter_00000", "meter_00001", "meter_00002"]


class TestDeterminism:
    """Seeded batch generation is reproducible."""

    def test_same_seed_same_output(self):
        df1 = generate(n=5, month=0, seed=42)
        df2 = generate(n=5, month=0, seed=42)
        assert df1.equals(df2)

    def test_different_seed_different_output(self):
        df1 = generate(n=5, month=0, seed=42)
        df2 = generate(n=5, month=0, seed=99)
        assert not df1["net"].equals(df2["net"])

    def test_seed_none_produces_randomness(self):
        df1 = generate(n=3, month=0, seed=None)
        df2 = generate(n=3, month=0, seed=None)
        # Extremely unlikely to be identical
        assert not df1["net"].equals(df2["net"])


class TestPerMeterVariation:
    """Same base type meters should differ due to latent perturbation."""

    def test_meters_differ(self):
        """Two meters of the same base type should not have identical profiles."""
        df = generate(n=10, archetype="colonial", fuel="oil", month=0, seed=42)
        # Get the first interval's base value for each meter
        first_interval = df[df["interval"] == 0].set_index("meter_id")["base"]
        # With 10 meters, we should see variation
        assert first_interval.nunique() > 1

    def test_meters_differ_in_net(self):
        df = generate(n=5, archetype="cape", fuel="gas", month=0, seed=42)
        peaks = df.groupby("meter_id")["net"].max()
        assert peaks.nunique() > 1


class TestDistribution:
    """Meter allocation across base types."""

    def test_fixed_archetype_fuel(self):
        """When archetype and fuel are specified, all meters are that type."""
        df = generate(n=20, archetype="ranch", fuel="gas", month=0)
        assert (df["archetype"] == "ranch").all()
        assert (df["fuel"] == "gas").all()

    def test_distributed_has_multiple_types(self):
        """When archetype=None, meters span multiple base types."""
        df = generate(n=200, archetype=None, fuel=None, month=0, seed=42)
        assert df["archetype"].nunique() > 1
        assert df["fuel"].nunique() > 1

    def test_uniform_distribution(self):
        """Uniform distribution should spread more evenly than empirical."""
        df_uniform = generate(
            n=960, archetype=None, fuel=None, month=0,
            distribution="uniform", seed=42,
        )
        # Count unique meters per base type (not rows — each meter has 96 rows)
        meters = df_uniform.drop_duplicates("meter_id")
        counts = meters.groupby(["archetype", "fuel", "der"]).size()
        # With 960 meters across 96 types, uniform should average ~10 each
        assert counts.max() < 30  # generous bound


class TestDERFlags:
    """DER configuration propagates correctly."""

    def test_solar_produces_negative_solar(self):
        df = generate(n=3, has_solar=True, month=6, seed=42)
        assert df["solar"].min() < 0

    def test_no_solar_zero(self):
        df = generate(n=3, has_solar=False, month=6, seed=42)
        assert (df["solar"] == 0.0).all()

    def test_ev_produces_charging(self):
        df = generate(n=3, has_ev=True, month=0, seed=42)
        assert df["ev"].max() > 0

    def test_no_ev_zero(self):
        df = generate(n=3, has_ev=False, month=0, seed=42)
        assert (df["ev"] == 0.0).all()


class TestFullYear:
    """Full-year generation specifics."""

    def test_365_days_per_meter(self):
        df = generate(n=1, month=None, seed=42)
        assert df["day_of_year"].nunique() == 365

    def test_all_months_covered(self):
        df = generate(n=1, month=None, seed=42)
        assert df["month"].nunique() == 12

    def test_month_assignment(self):
        """Day 0 should be month 0 (January), day 200 should be around month 6."""
        df = generate(n=1, month=None, seed=42)
        day0 = df[df["day_of_year"] == 0]["month"].iloc[0]
        day200 = df[df["day_of_year"] == 200]["month"].iloc[0]
        assert day0 == 0
        assert day200 == 6  # min(11, int(200/30.4)) = 6
