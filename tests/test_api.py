"""Tests for the FastAPI REST API."""

import pytest
from fastapi.testclient import TestClient

from opensynth_ne.api import app

client = TestClient(app)


class TestGenerateDay:
    def test_default_params(self):
        r = client.get("/api/generate/day")
        assert r.status_code == 200
        data = r.json()
        assert "points" in data
        assert "summary" in data
        assert len(data["points"]) == 96

    def test_summary_keys(self):
        r = client.get("/api/generate/day")
        s = r.json()["summary"]
        assert set(s.keys()) == {"temp", "irr", "peak", "peak_hour", "min", "kwh"}

    def test_custom_params(self):
        r = client.get("/api/generate/day", params={
            "archetype": "cape",
            "fuel": "gas",
            "month": 6,
            "has_solar": True,
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["points"]) == 96
        # Solar should have negative values in summer
        solar_vals = [p["solar"] for p in data["points"]]
        assert min(solar_vals) < 0

    def test_temp_override(self):
        r = client.get("/api/generate/day", params={"temp_f": 50})
        assert r.status_code == 200
        assert r.json()["summary"]["temp"] == 50

    def test_invalid_month(self):
        r = client.get("/api/generate/day", params={"month": 13})
        assert r.status_code == 422


class TestGenerateYear:
    def test_default(self):
        r = client.get("/api/generate/year")
        assert r.status_code == 200
        days = r.json()["days"]
        assert len(days) == 365

    def test_day_keys(self):
        r = client.get("/api/generate/year")
        day = r.json()["days"][0]
        assert set(day.keys()) == {"d", "m", "peak", "kwh", "temp", "min", "day_type"}

    def test_custom_archetype(self):
        r = client.get("/api/generate/year", params={"archetype": "antique"})
        assert r.status_code == 200
        assert len(r.json()["days"]) == 365


class TestGenerateBatch:
    def test_default(self):
        r = client.post("/api/generate/batch", json={"n": 3, "month": 0})
        assert r.status_code == 200
        data = r.json()
        assert data["meta"]["n"] == 3
        assert data["meta"]["rows"] == 3 * 96

    def test_batch_data_columns(self):
        r = client.post("/api/generate/batch", json={"n": 2, "month": 0})
        row = r.json()["data"][0]
        expected = {
            "meter_id", "archetype", "fuel", "der",
            "day_of_year", "month", "interval", "hour",
            "net", "gross", "base", "heat", "ev", "cool", "solar", "behav",
        }
        assert set(row.keys()) == expected

    def test_batch_cap(self):
        r = client.post("/api/generate/batch", json={"n": 2000})
        assert r.status_code == 422  # exceeds max of 1000


class TestValidation:
    def test_response_shape(self):
        r = client.get("/api/validation")
        assert r.status_code == 200
        data = r.json()
        assert "checks" in data
        assert "synth_distribution" in data
        assert "target_distribution" in data

    def test_check_count(self):
        r = client.get("/api/validation")
        assert len(r.json()["checks"]) == 6

    def test_one_failing_check(self):
        r = client.get("/api/validation")
        checks = r.json()["checks"]
        failing = [c for c in checks if not c["passing"]]
        assert len(failing) == 1
        assert failing[0]["id"] == "wkwh"

    def test_distribution_bins(self):
        r = client.get("/api/validation")
        assert len(r.json()["synth_distribution"]) == 24
        assert len(r.json()["target_distribution"]) == 24


class TestCatalog:
    def test_catalog_count(self):
        r = client.get("/api/catalog")
        assert r.status_code == 200
        catalog = r.json()["catalog"]
        assert len(catalog) == 96

    def test_catalog_row_keys(self):
        r = client.get("/api/catalog")
        row = r.json()["catalog"][0]
        assert "id" in row
        assert "archetype" in row
        assert "fuel" in row
        assert "der" in row
        assert "count" in row
        assert "sparkline" in row

    def test_sparkline_is_list(self):
        r = client.get("/api/catalog")
        row = r.json()["catalog"][0]
        assert isinstance(row["sparkline"], list)
        assert len(row["sparkline"]) == 24  # every 4th of 96 intervals
