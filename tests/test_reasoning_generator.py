"""
tests/test_reasoning_generator.py
------------------------------------
Unit tests for reasoning_generator.py.

Tests run entirely offline: no GEMINI_API_KEY needed. generate() itself
uses the rule-based fallback automatically when no key is set (same
behavior as production would have before the key is configured), and
the JSON-parsing / prompt-building helpers are tested directly with
crafted inputs — no live API call involved anywhere here.

Run with:
    pytest tests/test_reasoning_generator.py -v
"""

import pytest
from reasoning_generator import (
    generate,
    _sanitize_match_results,
    _compute_deterministic_fields,
    _parse_gemini_json,
    _fallback_reasoning,
)


def make_match_results():
    return [
        {"target_text": "Unit 1: Linear regression", "best_match_text": "Regression basics",
         "similarity": 0.81, "covered": True},
        {"target_text": "Unit 2: Neural networks", "best_match_text": None,
         "similarity": 0.30, "covered": False},
    ]


class TestSanitizeMatchResults:
    def test_strips_student_identifying_fields(self):
        dirty = [{
            "target_text": "Unit 1",
            "best_match_text": "Match A",
            "similarity": 0.9,
            "covered": True,
            "student_name": "John Doe",     # should NOT survive sanitization
            "student_id": "REC12345",       # should NOT survive sanitization
        }]
        clean = _sanitize_match_results(dirty)

        assert "student_name" not in clean[0]
        assert "student_id" not in clean[0]
        assert clean[0] == {
            "target_text": "Unit 1",
            "best_match_text": "Match A",
            "similarity": 0.9,
            "covered": True,
        }

    def test_handles_missing_optional_fields(self):
        sparse = [{"target_text": "Unit 1", "covered": False}]
        clean = _sanitize_match_results(sparse)
        assert clean[0] == {"target_text": "Unit 1", "covered": False}


class TestDeterministicFields:
    def test_missing_units_extracted_correctly(self):
        result = _compute_deterministic_fields(make_match_results(), 50.0, None, None)
        assert result["missing_units"] == ["Unit 2: Neural networks"]

    def test_overlap_pct_passes_through_unchanged(self):
        result = _compute_deterministic_fields(make_match_results(), 73.5, None, None)
        assert result["overlap_pct"] == 73.5

    def test_credit_difference_computed_when_both_given(self):
        result = _compute_deterministic_fields(make_match_results(), 50.0, 4, 3)
        assert result["credit_difference"] == 1

    def test_credit_difference_none_when_not_given(self):
        result = _compute_deterministic_fields(make_match_results(), 50.0, None, None)
        assert result["credit_difference"] is None

    def test_no_missing_units_when_all_covered(self):
        all_covered = [{"target_text": "Unit 1", "covered": True}]
        result = _compute_deterministic_fields(all_covered, 100.0, None, None)
        assert result["missing_units"] == []


class TestParseGeminiJson:
    def test_parses_plain_json(self):
        text = '{"narrative": "Looks good", "learning_outcomes_match": "full", "suggested_bridge_module": null}'
        parsed = _parse_gemini_json(text)
        assert parsed["narrative"] == "Looks good"

    def test_strips_markdown_fences(self):
        text = '```json\n{"narrative": "Looks good", "learning_outcomes_match": "full"}\n```'
        parsed = _parse_gemini_json(text)
        assert parsed["learning_outcomes_match"] == "full"

    def test_strips_fences_without_language_tag(self):
        text = '```\n{"narrative": "OK"}\n```'
        parsed = _parse_gemini_json(text)
        assert parsed["narrative"] == "OK"

    def test_malformed_json_raises(self):
        with pytest.raises(Exception):
            _parse_gemini_json("not valid json at all")


class TestFallbackReasoning:
    def test_accept_maps_to_full(self):
        result = _fallback_reasoning(100.0, "accept", [])
        assert result["learning_outcomes_match"] == "full"
        assert result["suggested_bridge_module"] is None

    def test_partial_maps_to_partial_with_bridge_suggestion(self):
        result = _fallback_reasoning(65.0, "partial", ["Unit 2: Neural networks"])
        assert result["learning_outcomes_match"] == "partial"
        assert result["suggested_bridge_module"] is not None
        assert "Unit 2" in result["suggested_bridge_module"]

    def test_redo_maps_to_none(self):
        result = _fallback_reasoning(10.0, "redo", ["Unit 1", "Unit 2"])
        assert result["learning_outcomes_match"] == "none"

    def test_narrative_mentions_coverage_and_status(self):
        result = _fallback_reasoning(65.0, "partial", ["Unit 2"])
        assert "65.0" in result["narrative"]
        assert "partial" in result["narrative"]


class TestGenerateEndToEnd:
    """Full generate() calls — run with no GEMINI_API_KEY set, so these
    exercise the real fallback path end-to-end, matching how the system
    behaves today before a key is configured."""

    def test_returns_all_required_keys(self):
        result = generate(make_match_results(), 50.0, "partial")
        expected_keys = {
            "overlap_pct", "learning_outcomes_match", "missing_units",
            "credit_difference", "suggested_bridge_module", "narrative",
        }
        assert set(result.keys()) == expected_keys

    def test_overlap_pct_matches_input(self):
        result = generate(make_match_results(), 50.0, "partial")
        assert result["overlap_pct"] == 50.0

    def test_missing_units_matches_uncovered_topics(self):
        result = generate(make_match_results(), 50.0, "partial")
        assert result["missing_units"] == ["Unit 2: Neural networks"]

    def test_credit_difference_populated_when_provided(self):
        result = generate(
            make_match_results(), 50.0, "partial",
            credit_hours_required=4, credit_hours_completed=2,
        )
        assert result["credit_difference"] == 2

    def test_full_coverage_no_missing_units(self):
        all_covered = [{"target_text": "Unit 1", "best_match_text": "Match",
                         "similarity": 0.9, "covered": True}]
        result = generate(all_covered, 100.0, "accept")
        assert result["missing_units"] == []
        assert result["learning_outcomes_match"] == "full"
