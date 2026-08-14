"""
tests/test_decision_engine.py
-------------------------------
Unit tests for decision_engine.decide().

Run with:
    pytest tests/test_decision_engine.py -v
"""

import pytest
from decision_engine import decide, status_to_color, decide_with_color


class TestFullMatch:
    def test_perfect_coverage(self):
        assert decide(100.0) == "accept"

    def test_high_coverage(self):
        assert decide(92.5) == "accept"

    def test_exactly_at_accept_threshold(self):
        # Boundary is inclusive: exactly 80% should accept, not partial.
        assert decide(80.0) == "accept"


class TestPartialMatch:
    def test_mid_coverage(self):
        assert decide(65.0) == "partial"

    def test_just_below_accept_threshold(self):
        assert decide(79.9) == "partial"

    def test_exactly_at_partial_threshold(self):
        # Boundary is inclusive: exactly 40% should be partial, not redo.
        assert decide(40.0) == "partial"


class TestNoMatch:
    def test_low_coverage(self):
        assert decide(10.0) == "redo"

    def test_zero_coverage(self):
        # e.g. empty transcript / zero topic overlap case from Aug 13's plan
        assert decide(0.0) == "redo"

    def test_just_below_partial_threshold(self):
        assert decide(39.9) == "redo"


class TestCustomThresholds:
    def test_stricter_accept_threshold(self):
        # With a 90% accept bar, 85% should now be partial, not accept.
        assert decide(85.0, accept_threshold=90.0) == "partial"

    def test_looser_partial_threshold(self):
        # With partial_threshold lowered to 20%, 25% should now be
        # partial instead of redo.
        assert decide(25.0, partial_threshold=20.0) == "partial"

    def test_custom_thresholds_full_range(self):
        assert decide(95.0, accept_threshold=90.0, partial_threshold=30.0) == "accept"
        assert decide(50.0, accept_threshold=90.0, partial_threshold=30.0) == "partial"
        assert decide(10.0, accept_threshold=90.0, partial_threshold=30.0) == "redo"


class TestColorMapping:
    def test_accept_is_green(self):
        assert status_to_color("accept") == "green"

    def test_partial_is_yellow(self):
        assert status_to_color("partial") == "yellow"

    def test_redo_is_red(self):
        assert status_to_color("redo") == "red"

    def test_unknown_status_raises(self):
        with pytest.raises(ValueError):
            status_to_color("maybe")


class TestDecideWithColor:
    def test_full_match_returns_green(self):
        result = decide_with_color(100.0)
        assert result == {"status": "accept", "color": "green"}

    def test_partial_match_returns_yellow(self):
        result = decide_with_color(65.0)
        assert result == {"status": "partial", "color": "yellow"}

    def test_no_match_returns_red(self):
        result = decide_with_color(10.0)
        assert result == {"status": "redo", "color": "red"}

    def test_respects_custom_thresholds(self):
        result = decide_with_color(85.0, accept_threshold=90.0)
        assert result == {"status": "partial", "color": "yellow"}


class TestInvalidInput:
    def test_coverage_above_100_raises(self):
        with pytest.raises(ValueError):
            decide(101.0)

    def test_coverage_below_0_raises(self):
        with pytest.raises(ValueError):
            decide(-5.0)

    def test_partial_threshold_not_lower_than_accept_raises(self):
        with pytest.raises(ValueError):
            decide(50.0, accept_threshold=50.0, partial_threshold=50.0)

    def test_partial_threshold_above_accept_raises(self):
        with pytest.raises(ValueError):
            decide(50.0, accept_threshold=40.0, partial_threshold=80.0)
