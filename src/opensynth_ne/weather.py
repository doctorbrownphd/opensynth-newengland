"""New England weather data and intensity functions."""

from __future__ import annotations

MONTHS: tuple[str, ...] = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

# Representative outdoor temperature (deg F) for New England by month.
MONTH_TEMP_F: tuple[int, ...] = (22, 25, 34, 46, 58, 68, 74, 72, 64, 52, 40, 28)

# Normalized solar irradiance by month (1.0 = July peak).
MONTH_IRRADIANCE: tuple[float, ...] = (
    0.34, 0.46, 0.62, 0.78, 0.9, 0.97,
    1.0, 0.92, 0.76, 0.56, 0.36, 0.28,
)


def heating_intensity(temp_f: float) -> float:
    """Heating demand proxy (0..1), linear from 60 deg F down to 0 deg F."""
    return max(0.0, min(1.0, (60.0 - temp_f) / 60.0))


def cooling_intensity(temp_f: float) -> float:
    """Cooling demand proxy (0..1), linear from 72 deg F up to 100 deg F."""
    return max(0.0, min(1.0, (temp_f - 72.0) / 28.0))
