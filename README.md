# OpenSynth New England

Synthetic AMI dataset generator for New England residential and small commercial load profiles. Built to complement the [LF Energy OpenSynth](https://www.lfenergy.org/) project.

## What This Is

**The gap:** Nearly every synthetic AMI dataset in existence reflects European grid conditions. North America is a blank spot. New England — with its aggressive winter peaks, high oil-heat penetration, and accelerating EV/solar adoption — is invisible.

**The fix:** A conditional generative model that produces realistic 15-minute interval smart meter profiles anchored to the New England regional profile, plus a static dataset of 10,000 synthetic meters.

## Two Deliverables

1. **Static dataset** — 10,000 synthetic residential smart meter profiles (15-min intervals, full year, 96 base types), CC-BY 4.0, Hive-partitioned Parquet. Build it locally with `scripts/export_dataset.py`.

2. **Conditional generator** — a Python package that produces new synthetic profiles on demand, conditioned on housing archetype, heating fuel, weather, and DER.

## Quick Start

```bash
pip install -e .   # from a clone of this repo

from opensynth_ne import generate_day, generate

# Single day, interactive exploration
df, summary = generate_day(
    archetype="colonial",
    fuel="oil",
    month=0,        # January
    temp_f=22,
    has_ev=True,
    has_solar=True,
)
# df: 96 rows × 10 columns (interval, hour, net, gross, base, heat, ev, cool, solar, behav)

# Batch: 100 meters × full year
dataset = generate(n=100, archetype="colonial", fuel="oil")
# dataset: 3,504,000 rows (100 × 365 × 96) — long/tidy format
```

## Conditioning Variables

| Variable | Values |
|----------|--------|
| Archetype | Colonial, Cape, Ranch, Multi-family, Antique, Split-level, Contemporary, Mobile home |
| Fuel type | Oil heat, Natural gas, Electric resistance, Heat pump |
| DER | Rooftop solar, EV charging, Battery storage (boolean flags) |
| Month | 1-12 |
| Temperature | Continuous (°F), defaults to regional monthly average |

## Showcase Web App

A React + FastAPI application demonstrates the generator interactively.

```bash
# Terminal 1: API server
pip install -e ".[api]"
uvicorn opensynth_ne.api:app --port 8000

# Terminal 2: Frontend dev server
cd web && npm install && npm run dev
```

Production (single process):
```bash
cd web && npm run build
opensynth-ne  # serves API + frontend on :8000
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v  # 107+ tests
```

## Validation

Each dataset release is checked against regional statistics from independent sources. The values below are the current reference results in `src/opensynth_ne/validation.py`, recorded for the v0 model. They will be rerun for the trained CVAE.

| Metric | Source | Target | v0 result |
|--------|--------|--------|--------|
| Annual kWh distribution | EIA RECS | Within 5% | Pass (+3.9%) |
| Winter peak timing | ISO-NE | Within 1 hour | Pass (0.5 h) |
| Summer load-shape correlation | ISO-NE | > 0.85 | Pass (0.91) |
| EV charging signature | Published studies | Peak 23:00–04:00 | Pass |
| Solar generation shape | NREL PVWatts | Within 10% | Pass (+7.5%) |
| Winter kWh (oil-heat homes) | EIA RECS | Within 8% | Open (28% gap; electricity is only auxiliary load in oil-heated homes) |

## License

Apache-2.0 (code), CC-BY 4.0 (dataset)
