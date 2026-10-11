"""Fetch ISO-NE hourly demand data from the EIA API.

Downloads a full year of hourly system demand for ISO New England,
computes daily/monthly statistics, and saves reference distributions
for CVAE calibration.

Usage:
    python training/fetch_isone.py --year 2023
    python training/fetch_isone.py --year 2024
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

# EIA Open Data API — DEMO_KEY has rate limits but works for this volume
API_BASE = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
API_KEY = "DEMO_KEY"
OUTPUT_DIR = Path(__file__).parent / "reference_data"


def fetch_chunk(start: str, end: str, offset: int = 0, length: int = 5000) -> list[dict]:
    """Fetch one chunk of hourly data from EIA API."""
    import urllib.request
    import urllib.parse

    params = urllib.parse.urlencode({
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": "ISNE",
        "facets[type][]": "D",
        "start": start,
        "end": end,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": offset,
        "length": length,
        "api_key": API_KEY,
    })

    url = f"{API_BASE}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "OpenSynth-NE/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    return data.get("response", {}).get("data", [])


def fetch_year(year: int) -> pd.DataFrame:
    """Fetch all hourly demand data for one year."""
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    all_rows = []
    offset = 0
    chunk_size = 5000

    print(f"Fetching ISO-NE hourly demand for {year}...")

    while True:
        print(f"  offset={offset}...", end="", flush=True)
        rows = fetch_chunk(start, end, offset=offset, length=chunk_size)
        print(f" got {len(rows)} rows")
        all_rows.extend(rows)

        if len(rows) < chunk_size:
            break
        offset += chunk_size
        time.sleep(1)  # rate limit courtesy

    print(f"  Total: {len(all_rows)} hourly records")

    df = pd.DataFrame(all_rows)
    df["period"] = pd.to_datetime(df["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df = df.sort_values("period").reset_index(drop=True)

    # Rename for clarity
    df = df.rename(columns={"value": "demand_mwh"})
    df["month"] = df["period"].dt.month - 1  # 0-indexed to match our model
    df["hour"] = df["period"].dt.hour
    df["day_of_year"] = df["period"].dt.dayofyear - 1
    df["weekday"] = df["period"].dt.weekday  # 0=Mon, 6=Sun

    return df[["period", "demand_mwh", "month", "hour", "day_of_year", "weekday"]]


def compute_statistics(df: pd.DataFrame) -> dict:
    """Compute reference statistics for model calibration."""
    stats = {}

    # Annual total
    annual_mwh = df["demand_mwh"].sum()
    n_hours = len(df)
    stats["annual_mwh"] = round(annual_mwh, 0)
    stats["n_hours"] = n_hours

    # Monthly statistics
    monthly = df.groupby("month").agg(
        mean_hourly_mw=("demand_mwh", "mean"),
        peak_mw=("demand_mwh", "max"),
        total_mwh=("demand_mwh", "sum"),
    ).round(1)
    stats["monthly"] = monthly.to_dict(orient="index")

    # Hourly profile by month (average load shape)
    hourly_shape = df.groupby(["month", "hour"])["demand_mwh"].mean().round(1)
    stats["hourly_shape"] = {
        f"month_{m}": hourly_shape.loc[m].tolist()
        for m in range(12) if m in hourly_shape.index.get_level_values(0)
    }

    # Winter peak (Dec-Feb)
    winter = df[df["month"].isin([0, 1, 11])]
    if len(winter) > 0:
        winter_peak_idx = winter["demand_mwh"].idxmax()
        winter_peak_hour = winter.loc[winter_peak_idx, "hour"]
        stats["winter_peak_mw"] = round(winter["demand_mwh"].max(), 1)
        stats["winter_peak_hour"] = int(winter_peak_hour)

    # Summer peak (Jun-Aug)
    summer = df[df["month"].isin([5, 6, 7])]
    if len(summer) > 0:
        stats["summer_peak_mw"] = round(summer["demand_mwh"].max(), 1)

    # Weekday vs weekend load ratio
    wd = df[df["weekday"] < 5]["demand_mwh"].mean()
    we = df[df["weekday"] >= 5]["demand_mwh"].mean()
    stats["weekday_mean_mw"] = round(wd, 1)
    stats["weekend_mean_mw"] = round(we, 1)
    stats["weekend_weekday_ratio"] = round(we / wd, 3)

    # Per-customer estimates (ISO-NE serves ~6.8M customers)
    # Average residential customer uses ~600 kWh/month
    n_customers_est = 6_800_000
    stats["est_customers"] = n_customers_est
    stats["est_annual_kwh_per_customer"] = round(annual_mwh * 1000 / n_customers_est, 0)

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2023)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = fetch_year(args.year)

    # Save raw data
    csv_path = OUTPUT_DIR / f"isone_hourly_{args.year}.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nSaved {len(df)} rows to {csv_path}")

    # Compute and save statistics
    stats = compute_statistics(df)
    stats_path = OUTPUT_DIR / f"isone_stats_{args.year}.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2, default=lambda x: int(x) if hasattr(x, 'item') else x)
    print(f"Saved statistics to {stats_path}")

    # Print summary
    print(f"\n--- ISO-NE {args.year} Summary ---")
    print(f"  Hours:          {stats['n_hours']:,}")
    print(f"  Annual MWh:     {stats['annual_mwh']:,.0f}")
    print(f"  Est kWh/cust:   {stats['est_annual_kwh_per_customer']:,.0f}")
    if "winter_peak_mw" in stats:
        print(f"  Winter peak:    {stats['winter_peak_mw']:,.0f} MW at hour {stats['winter_peak_hour']}")
    if "summer_peak_mw" in stats:
        print(f"  Summer peak:    {stats['summer_peak_mw']:,.0f} MW")
    print(f"  WE/WD ratio:    {stats['weekend_weekday_ratio']:.3f}")


if __name__ == "__main__":
    main()
