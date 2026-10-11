# Pecan Street Dataport Integration

This directory contains the pipeline for ingesting real residential load
profiles from Pecan Street Dataport into the CVAE training data.

## Setup

1. Get a Dataport license at https://www.pecanstreet.org/dataport/
2. Download 15-minute electricity data via the Dataport web query interface:
   - Table: `electricity.eg_realpower_15min`
   - Select all available homes
   - Date range: full year (e.g., 2022-01-01 to 2022-12-31)
   - Export as CSV
3. Place the CSV file in this directory as `raw_15min.csv`
4. Run the ingestion: `python ingest.py`
5. Run the merged training: `python train_with_real.py`

## What the Pipeline Does

1. **ingest.py** — reads Pecan Street CSV, cleans, aligns to our 96-interval
   daily format, decomposes into load components, maps to NE archetypes
2. **train_with_real.py** — merges real profiles with mock profiles for
   CVAE training, using real data for distribution calibration
