"""Tests for weather data and intensity functions."""

import pytest

from opensynth_ne.weather import (
    MONTH_IRRADIANCE,
    MONTH_TEMP_F,
    MONTHS,
    cooling_intensity,
    heating_intensity,
)


def test_month_count():
    assert len(MONTHS) == 12
    assert len(MONTH_TEMP_F) == 12
    assert len(MONTH_IRRADIANCE) == 12


def test_january_is_coldest_region():
    # Jan (22F) should be near the coldest; Jul (74F) warmest
    assert MONTH_TEMP_F[0] < MONTH_TEMP_F[6]


def test_july_peak_irradiance():
    assert MONTH_IRRADIANCE[6] == 1.0
    assert all(v <= 1.0 for v in MONTH_IRRADIANCE)


def test_heating_intensity_cold():
    # At 22F: (60-22)/60 = 0.6333...
    assert heating_intensity(22) == pytest.approx(0.6333, abs=0.001)


def test_heating_intensity_warm():
    # At 70F: no heating needed
    assert heating_intensity(70) == 0.0


def test_heating_intensity_extreme_cold():
    # At -10F: clamped to 1.0
    assert heating_intensity(-10) == 1.0


def test_heating_intensity_boundary():
    assert heating_intensity(60) == 0.0


def test_cooling_intensity_hot():
    # At 74F: (74-72)/28 = 0.0714...
    assert cooling_intensity(74) == pytest.approx(0.0714, abs=0.001)


def test_cooling_intensity_cool():
    # At 50F: no cooling needed
    assert cooling_intensity(50) == 0.0


def test_cooling_intensity_extreme_hot():
    # At 100F: clamped to 1.0
    assert cooling_intensity(100) == 1.0


def test_cooling_intensity_boundary():
    assert cooling_intensity(72) == 0.0
