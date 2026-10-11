"""Tests for validation checks and distribution function."""

from opensynth_ne.validation import CHECKS, distribution, validate


class TestChecks:
    def test_check_count(self):
        assert len(CHECKS) == 6

    def test_one_failing(self):
        failing = [c for c in CHECKS if not c.passing]
        assert len(failing) == 1
        assert failing[0].id == "wkwh"

    def test_five_passing(self):
        passing = [c for c in CHECKS if c.passing]
        assert len(passing) == 5

    def test_validate_returns_list(self):
        result = validate()
        assert isinstance(result, list)
        assert len(result) == 6

    def test_failing_check_details(self):
        wkwh = next(c for c in CHECKS if c.id == "wkwh")
        assert wkwh.target_val == 1180
        assert wkwh.synth_val == 850
        assert wkwh.delta == 28.0
        assert wkwh.passing is False

    def test_all_checks_have_required_fields(self):
        for c in CHECKS:
            assert c.id
            assert c.metric
            assert c.source
            assert c.target
            assert c.unit


class TestDistribution:
    def test_bin_count(self):
        bins = distribution(11, 8612, 2100, 24)
        assert len(bins) == 24

    def test_total_samples(self):
        bins = distribution(11, 8612, 2100, 24)
        assert sum(bins) == 4000

    def test_deterministic(self):
        bins1 = distribution(11, 8612, 2100, 24)
        bins2 = distribution(11, 8612, 2100, 24)
        assert bins1 == bins2

    def test_different_seed_different_bins(self):
        bins1 = distribution(11, 8612, 2100, 24)
        bins2 = distribution(42, 8460, 1950, 24)
        assert bins1 != bins2

    def test_bell_shaped(self):
        """Middle bins should have more samples than edge bins."""
        bins = distribution(11, 8612, 2100, 24)
        middle = sum(bins[10:14])
        edges = bins[0] + bins[1] + bins[-2] + bins[-1]
        assert middle > edges

    def test_all_bins_nonnegative(self):
        bins = distribution(11, 8612, 2100, 24)
        assert all(b >= 0 for b in bins)
