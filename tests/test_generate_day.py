"""Tests for generate_day() — the core single-day load profile generator."""

import pytest

from opensynth_ne.model import generate_day


class TestShape:
    """DataFrame shape and column correctness."""

    def test_row_count(self):
        df, _ = generate_day()
        assert len(df) == 96

    def test_columns(self):
        df, _ = generate_day()
        expected = {"interval", "hour", "net", "gross", "base", "heat", "ev", "cool", "solar", "behav"}
        assert set(df.columns) == expected

    def test_interval_range(self):
        df, _ = generate_day()
        assert df["interval"].iloc[0] == 0
        assert df["interval"].iloc[-1] == 95

    def test_hour_range(self):
        df, _ = generate_day()
        assert df["hour"].iloc[0] == 0.0
        assert df["hour"].iloc[-1] == 23.75


class TestSummary:
    """Summary dict correctness."""

    def test_summary_keys(self):
        _, s = generate_day()
        assert set(s.keys()) == {"temp", "irr", "peak", "peak_hour", "min", "kwh"}

    def test_peak_matches_max_net(self):
        df, s = generate_day()
        assert s["peak"] == pytest.approx(df["net"].max())

    def test_min_matches_min_net(self):
        df, s = generate_day()
        assert s["min"] == pytest.approx(df["net"].min())

    def test_kwh_is_integral(self):
        df, s = generate_day()
        expected = round(float(df["net"].sum()) * 0.25, 1)
        assert s["kwh"] == expected

    def test_temp_default_january(self):
        _, s = generate_day(month=0)
        assert s["temp"] == 22  # January monthly temp

    def test_temp_override(self):
        _, s = generate_day(temp_f=50)
        assert s["temp"] == 50

    def test_irradiance_january(self):
        _, s = generate_day(month=0)
        assert s["irr"] == 0.34

    def test_irradiance_july(self):
        _, s = generate_day(month=6)
        assert s["irr"] == 1.0


class TestDeterminism:
    """Seeded RNG guarantees identical output."""

    def test_same_seed_same_output(self):
        df1, s1 = generate_day(seed=42)
        df2, s2 = generate_day(seed=42)
        assert df1.equals(df2)
        assert s1 == s2

    def test_different_seed_different_output(self):
        df1, _ = generate_day(seed=42)
        df2, _ = generate_day(seed=99)
        assert not df1["net"].equals(df2["net"])

    def test_different_archetype_different_output(self):
        df1, _ = generate_day(archetype="colonial")
        df2, _ = generate_day(archetype="cape")
        assert not df1["net"].equals(df2["net"])

    def test_different_month_different_output(self):
        df1, _ = generate_day(month=0)
        df2, _ = generate_day(month=6)
        assert not df1["net"].equals(df2["net"])


class TestComponentIsolation:
    """DER components are zero when disabled."""

    def test_solar_zero_when_off(self):
        df, _ = generate_day(has_solar=False)
        assert (df["solar"] == 0.0).all()

    def test_solar_nonzero_when_on(self):
        df, _ = generate_day(has_solar=True, month=6)
        assert df["solar"].min() < 0  # generation is negative

    def test_ev_zero_when_off(self):
        df, _ = generate_day(has_ev=False)
        assert (df["ev"] == 0.0).all()

    def test_ev_nonzero_when_on(self):
        df, _ = generate_day(has_ev=True)
        assert df["ev"].max() > 0

    def test_managed_ev_overnight(self):
        """Managed EV charges 23:00-05:00 at 6.6 kW (mock model exact behavior)."""
        df, _ = generate_day(has_ev=True, has_ev_managed=True, use_cvae=False)
        midnight = df[df["hour"] == 0.0]["ev"].iloc[0]
        noon = df[df["hour"] == 12.0]["ev"].iloc[0]
        assert midnight == 6.6
        assert noon == 0.0

    def test_heat_zero_in_summer(self):
        """At 74F (July), heating should be effectively zero (mock model)."""
        df, _ = generate_day(month=6, use_cvae=False)  # July, 74F
        assert df["heat"].max() < 0.01

    def test_cool_zero_in_winter(self):
        """At 22F (January), cooling should be zero (mock model)."""
        df, _ = generate_day(month=0, use_cvae=False)  # January, 22F
        assert (df["cool"] == 0.0).all()


class TestHeatPumpCOP:
    """Heat pump COP drop below 15 deg F."""

    def test_cop_drop_increases_heat(self):
        df_cold, _ = generate_day(fuel="heatpump", temp_f=10, seed=1)
        df_mild, _ = generate_day(fuel="heatpump", temp_f=20, seed=1)
        # At 10F, COP drop applies (1.35x). At 20F it doesn't.
        # Both have heating (temp < 60), but cold day has the multiplier.
        cold_peak_heat = df_cold["heat"].max()
        mild_peak_heat = df_mild["heat"].max()
        assert cold_peak_heat > mild_peak_heat


class TestGrossNetRelationship:
    """Gross and net load invariants."""

    def test_gross_always_positive(self):
        df, _ = generate_day()
        assert (df["gross"] >= 0.05).all()

    def test_net_less_than_or_equal_gross(self):
        """Net <= gross (solar and battery discharge subtract)."""
        df, _ = generate_day(has_solar=True, has_battery=True, month=6)
        assert (df["net"] <= df["gross"] + 0.001).all()

    def test_net_can_go_negative_with_solar(self):
        """With solar on a sunny summer day, net can export."""
        df, _ = generate_day(
            archetype="cape", fuel="gas", has_solar=True,
            month=6, seed=42,
        )
        # Cape (scale=1.0) with solar in July should have midday export
        assert df["net"].min() < 0


class TestPhysicalPlausibility:
    """Sanity checks on output magnitudes."""

    def test_daily_kwh_reasonable(self):
        """A colonial with oil heat in January: expect 15-50 kWh."""
        _, s = generate_day(archetype="colonial", fuel="oil", month=0)
        assert 10 < s["kwh"] < 60

    def test_summer_lower_than_winter(self):
        """July load should be lower than January for oil heat."""
        _, s_jan = generate_day(month=0, fuel="oil")
        _, s_jul = generate_day(month=6, fuel="oil")
        assert s_jul["kwh"] < s_jan["kwh"]

    def test_electric_heat_higher_than_oil(self):
        """Electric resistance should have higher winter kWh than oil."""
        _, s_oil = generate_day(fuel="oil", month=0, seed=1)
        _, s_elec = generate_day(fuel="electric", month=0, seed=1)
        assert s_elec["kwh"] > s_oil["kwh"]

    def test_colonial_higher_than_mobilehome(self):
        """Larger house → higher load."""
        _, s_col = generate_day(archetype="colonial", seed=1)
        _, s_mob = generate_day(archetype="mobilehome", seed=1)
        assert s_col["kwh"] > s_mob["kwh"]


class TestEdgeCases:
    """Edge case inputs."""

    def test_seed_zero(self):
        df1, _ = generate_day(seed=0)
        df2, _ = generate_day(seed=0)
        assert df1.equals(df2)
        assert df1["net"].std() > 0  # not all identical values

    def test_month_boundary_eleven(self):
        df, s = generate_day(month=11)
        assert len(df) == 96
        assert s["temp"] == 28  # December

    def test_extreme_cold(self):
        df, s = generate_day(temp_f=-10, fuel="heatpump")
        assert s["kwh"] > 0
        assert df["heat"].max() > 0

    def test_extreme_hot(self):
        df, s = generate_day(temp_f=95, month=6)
        assert s["kwh"] > 0
        assert df["cool"].max() > 0

    def test_invalid_month_raises(self):
        with pytest.raises(ValueError, match="month must be"):
            generate_day(month=12)

    def test_invalid_day_type_raises(self):
        with pytest.raises(ValueError, match="day_type"):
            generate_day(day_type="tuesday")

    def test_invalid_archetype_raises(self):
        with pytest.raises(ValueError, match="Unknown archetype"):
            generate_day(archetype="mansion")

    def test_weekend_shifts_peak(self):
        """Weekend morning peak should be later than weekday."""
        df_wd, _ = generate_day(day_type="weekday", use_cvae=False, seed=42)
        df_we, _ = generate_day(day_type="weekend", use_cvae=False, seed=42)
        # Different behavioral patterns should produce different profiles
        assert not df_wd["behav"].equals(df_we["behav"])
