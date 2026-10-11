"""FastAPI application — REST API and static file serving."""

from __future__ import annotations

import os
import pathlib
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from opensynth_ne.archetypes import ARCHETYPES, DER_CONFIGS, FUELS, get_archetype, get_fuel
from opensynth_ne.model import (
    build_catalog,
    generate,
    generate_day,
    generate_year,
)
from opensynth_ne.validation import distribution, validate

app = FastAPI(
    title="OpenSynth New England",
    version="0.1.0",
    description="Synthetic AMI load profile generator for New England",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Valid string values for validation
_VALID_ARCHETYPES = frozenset(a.id for a in ARCHETYPES)
_VALID_FUELS = frozenset(f.id for f in FUELS)
_VALID_DAY_TYPES = frozenset(("weekday", "weekend", "holiday"))


def _validate_archetype(v: str) -> None:
    if v not in _VALID_ARCHETYPES:
        raise HTTPException(400, f"Unknown archetype '{v}'. Valid: {sorted(_VALID_ARCHETYPES)}")


def _validate_fuel(v: str) -> None:
    if v not in _VALID_FUELS:
        raise HTTPException(400, f"Unknown fuel '{v}'. Valid: {sorted(_VALID_FUELS)}")


def _validate_day_type(v: str) -> None:
    if v not in _VALID_DAY_TYPES:
        raise HTTPException(400, f"Unknown day_type '{v}'. Valid: {sorted(_VALID_DAY_TYPES)}")


# ---------------------------------------------------------------------------
# GET /api/generate/day
# ---------------------------------------------------------------------------


@app.get("/api/generate/day")
def api_generate_day(
    archetype: str = Query("colonial"),
    fuel: str = Query("oil"),
    month: int = Query(0, ge=0, le=11),
    temp_f: float | None = Query(None),
    has_ev: bool = Query(False),
    has_solar: bool = Query(False),
    has_battery: bool = Query(False),
    has_ev_managed: bool = Query(True),
    day_type: str = Query("weekday"),
    seed: int = Query(42),
) -> dict:
    """Generate a single representative day of 15-min interval load data."""
    _validate_archetype(archetype)
    _validate_fuel(fuel)
    _validate_day_type(day_type)

    df, summary = generate_day(
        archetype=archetype,
        fuel=fuel,
        month=month,
        temp_f=temp_f,
        has_ev=has_ev,
        has_solar=has_solar,
        has_battery=has_battery,
        has_ev_managed=has_ev_managed,
        day_type=day_type,
        seed=seed,
    )
    return {
        "points": df.to_dict(orient="records"),
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# GET /api/generate/year
# ---------------------------------------------------------------------------


@app.get("/api/generate/year")
def api_generate_year(
    archetype: str = Query("colonial"),
    fuel: str = Query("oil"),
    has_ev: bool = Query(False),
    has_solar: bool = Query(False),
    has_battery: bool = Query(False),
    has_ev_managed: bool = Query(True),
    seed: int = Query(7),
) -> dict:
    """Generate 365-day peak/energy/temp series for the seasonal chart."""
    _validate_archetype(archetype)
    _validate_fuel(fuel)

    days = generate_year(
        archetype=archetype,
        fuel=fuel,
        has_ev=has_ev,
        has_solar=has_solar,
        has_battery=has_battery,
        has_ev_managed=has_ev_managed,
        seed=seed,
    )
    return {"days": days}


# ---------------------------------------------------------------------------
# POST /api/generate/batch
# ---------------------------------------------------------------------------


class BatchRequest(BaseModel):
    n: int = Field(100, ge=1, le=1000)
    archetype: str | None = "colonial"
    fuel: str | None = "oil"
    month: int | None = Field(None, ge=0, le=11)
    temp_f: float | None = None
    has_ev: bool = False
    has_solar: bool = False
    has_battery: bool = False
    has_ev_managed: bool = True
    distribution: str = "empirical"
    seed: int = 42


@app.post("/api/generate/batch")
def api_generate_batch(body: BatchRequest) -> dict:
    """Generate batch load profiles for multiple meters."""
    if body.archetype is not None:
        _validate_archetype(body.archetype)
    if body.fuel is not None:
        _validate_fuel(body.fuel)

    df = generate(
        n=body.n,
        archetype=body.archetype,
        fuel=body.fuel,
        month=body.month,
        temp_f=body.temp_f,
        has_ev=body.has_ev,
        has_solar=body.has_solar,
        has_battery=body.has_battery,
        has_ev_managed=body.has_ev_managed,
        distribution=body.distribution,
        seed=body.seed,
    )
    return {
        "data": df.to_dict(orient="records"),
        "meta": {
            "n": int(df["meter_id"].nunique()),
            "rows": len(df),
        },
    }


# ---------------------------------------------------------------------------
# GET /api/validation
# ---------------------------------------------------------------------------


@app.get("/api/validation")
def api_validation() -> dict:
    """Return validation checks and distribution data for the histogram."""
    checks = validate()
    return {
        "checks": [asdict(c) for c in checks],
        "synth_distribution": distribution(11, 8788, 2100, 24),
        "target_distribution": distribution(42, 8460, 1950, 24),
    }


# ---------------------------------------------------------------------------
# GET /api/catalog
# ---------------------------------------------------------------------------


@app.get("/api/metadata")
def api_metadata() -> dict:
    """Return valid archetypes, fuels, DER configs, and day types."""
    return {
        "archetypes": [{"id": a.id, "label": a.label, "sqft": a.sqft} for a in ARCHETYPES],
        "fuels": [{"id": f.id, "label": f.label} for f in FUELS],
        "der_configs": [{"id": d.id, "label": d.label, "ev": d.ev, "solar": d.solar, "battery": d.battery} for d in DER_CONFIGS],
        "day_types": sorted(_VALID_DAY_TYPES),
    }


@app.get("/api/catalog")
def api_catalog() -> dict:
    """Return the 96 base-type catalog with sparkline data."""
    return {"catalog": build_catalog()}


# ---------------------------------------------------------------------------
# Static file mount — serves web/dist/ in production
# ---------------------------------------------------------------------------

_web_dist = pathlib.Path(__file__).parent.parent.parent / "web" / "dist"
if _web_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="static")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the API server (used by the opensynth-ne CLI command)."""
    import uvicorn

    host = os.getenv("OPENSYNTH_HOST", "0.0.0.0")
    port = int(os.getenv("OPENSYNTH_PORT", "8000"))
    uvicorn.run("opensynth_ne.api:app", host=host, port=port)
