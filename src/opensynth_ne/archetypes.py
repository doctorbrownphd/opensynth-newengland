"""Housing archetypes, fuel types, and DER configurations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Archetype:
    """A New England housing type that determines baseline load shape and scale."""

    id: str
    label: str
    sqft: int
    scale: float


@dataclass(frozen=True, slots=True)
class FuelType:
    """Primary heating fuel — determines the electric share of heating load."""

    id: str
    label: str
    e_heat: float  # fraction of heating demand that is electric (0..1)


@dataclass(frozen=True, slots=True)
class DERConfig:
    """Distributed energy resource configuration for a meter."""

    id: str
    label: str
    ev: bool
    solar: bool
    battery: bool


ARCHETYPES: tuple[Archetype, ...] = (
    Archetype("colonial", "Colonial", 2400, 1.35),
    Archetype("cape", "Cape", 1500, 1.0),
    Archetype("ranch", "Ranch", 1700, 1.1),
    Archetype("multifamily", "Multi-family", 950, 0.7),
    Archetype("antique", "Antique (pre-1900)", 2100, 1.45),
    Archetype("splitlevel", "Split-level", 1900, 1.15),
    Archetype("contemporary", "Contemporary", 2600, 1.05),
    Archetype("mobilehome", "Mobile home", 1050, 0.85),
)

FUELS: tuple[FuelType, ...] = (
    # e_heat: fraction of space heating met by electricity
    # Oil/gas: electric auxiliary (baseboard, space heaters) in NE
    # Source: EIA RECS Table CE4.2, NE end-use estimates
    FuelType("oil", "Oil heat", 0.25),
    FuelType("gas", "Natural gas", 0.15),
    FuelType("electric", "Electric resistance", 1.0),
    FuelType("heatpump", "Heat pump", 0.55),
)

DER_CONFIGS: tuple[DERConfig, ...] = (
    DERConfig("none", "No DER", ev=False, solar=False, battery=False),
    DERConfig("solar", "Solar", ev=False, solar=True, battery=False),
    DERConfig("solar_ev", "Solar + EV", ev=True, solar=True, battery=True),
)

_ARCH_INDEX = {a.id: a for a in ARCHETYPES}
_FUEL_INDEX = {f.id: f for f in FUELS}
_DER_INDEX = {d.id: d for d in DER_CONFIGS}


def get_archetype(id: str) -> Archetype:
    """Look up an archetype by ID. Raises ValueError if not found."""
    try:
        return _ARCH_INDEX[id]
    except KeyError:
        valid = ", ".join(_ARCH_INDEX)
        raise ValueError(f"Unknown archetype '{id}'. Valid: {valid}") from None


def get_fuel(id: str) -> FuelType:
    """Look up a fuel type by ID. Raises ValueError if not found."""
    try:
        return _FUEL_INDEX[id]
    except KeyError:
        valid = ", ".join(_FUEL_INDEX)
        raise ValueError(f"Unknown fuel type '{id}'. Valid: {valid}") from None


def get_der_config(id: str) -> DERConfig:
    """Look up a DER configuration by ID. Raises ValueError if not found."""
    try:
        return _DER_INDEX[id]
    except KeyError:
        valid = ", ".join(_DER_INDEX)
        raise ValueError(f"Unknown DER config '{id}'. Valid: {valid}") from None


def base_type_count() -> int:
    """Total number of base types: archetypes x fuels x DER configs = 96."""
    return len(ARCHETYPES) * len(FUELS) * len(DER_CONFIGS)
