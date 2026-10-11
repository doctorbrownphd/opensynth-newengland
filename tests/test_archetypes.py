"""Tests for housing archetypes, fuel types, and DER configurations."""

import pytest

from opensynth_ne.archetypes import (
    ARCHETYPES,
    DER_CONFIGS,
    FUELS,
    base_type_count,
    get_archetype,
    get_der_config,
    get_fuel,
)


def test_archetype_count():
    assert len(ARCHETYPES) == 8


def test_fuel_count():
    assert len(FUELS) == 4


def test_der_config_count():
    assert len(DER_CONFIGS) == 3


def test_base_type_count():
    assert base_type_count() == 96


def test_archetype_lookup():
    colonial = get_archetype("colonial")
    assert colonial.sqft == 2400
    assert colonial.scale == 1.35


def test_fuel_lookup():
    hp = get_fuel("heatpump")
    assert hp.e_heat == 0.55
    assert hp.label == "Heat pump"


def test_der_lookup():
    solar_ev = get_der_config("solar_ev")
    assert solar_ev.ev is True
    assert solar_ev.solar is True
    assert solar_ev.battery is True


def test_der_none():
    none = get_der_config("none")
    assert none.ev is False
    assert none.solar is False
    assert none.battery is False


def test_archetype_unknown():
    with pytest.raises(ValueError, match="Unknown archetype"):
        get_archetype("mansion")


def test_fuel_unknown():
    with pytest.raises(ValueError, match="Unknown fuel type"):
        get_fuel("coal")


def test_der_unknown():
    with pytest.raises(ValueError, match="Unknown DER config"):
        get_der_config("wind")


def test_all_archetype_ids_unique():
    ids = [a.id for a in ARCHETYPES]
    assert len(ids) == len(set(ids))


def test_all_fuel_ids_unique():
    ids = [f.id for f in FUELS]
    assert len(ids) == len(set(ids))


def test_all_scales_positive():
    for a in ARCHETYPES:
        assert a.scale > 0


def test_all_e_heat_in_range():
    for f in FUELS:
        assert 0.0 <= f.e_heat <= 1.0
