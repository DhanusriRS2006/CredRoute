"""
tests/test_matching_engine.py
--------------------------------
Unit tests for matching_engine.match_course().

Deliberately uses hand-crafted embedding vectors instead of the real
sentence-transformers model — this keeps tests instant, deterministic,
and runnable offline (no model download). The embedding model itself
is already sanity-checked separately in embed_topics.py's own test.

Run with:
    pytest tests/test_matching_engine.py -v
"""

import pytest
from matching_engine import match_course, _cosine_similarity, allocate_across_courses


# Hand-crafted vectors with known relationships:
IDENTICAL_A = [1.0, 0.0, 0.0]
IDENTICAL_B = [1.0, 0.0, 0.0]   # same direction as IDENTICAL_A -> similarity 1.0
ORTHOGONAL = [0.0, 1.0, 0.0]    # perpendicular to IDENTICAL_A -> similarity 0.0
OPPOSITE = [-1.0, 0.0, 0.0]     # opposite direction -> similarity -1.0
PARTIAL = [0.7, 0.7, 0.0]       # ~45 degrees from IDENTICAL_A -> similarity ~0.707


def topic(text, embedding):
    return {"text": text, "embedding": embedding}


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity(IDENTICAL_A, IDENTICAL_B) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity(IDENTICAL_A, ORTHOGONAL) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert _cosine_similarity(IDENTICAL_A, OPPOSITE) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        # Guards against division by zero rather than crashing.
        assert _cosine_similarity([0.0, 0.0, 0.0], IDENTICAL_A) == 0.0


class TestFullMatch:
    def test_all_targets_covered(self):
        target_topics = [topic("Target A", IDENTICAL_A)]
        pooled_topics = [topic("Source A", IDENTICAL_B)]

        results, coverage = match_course(target_topics, pooled_topics, topic_threshold=0.75)

        assert coverage == 100.0
        assert results[0]["covered"] is True
        assert results[0]["similarity"] == pytest.approx(1.0)
        assert results[0]["best_match_text"] == "Source A"

    def test_multiple_targets_all_covered(self):
        target_topics = [topic("T1", IDENTICAL_A), topic("T2", IDENTICAL_B)]
        pooled_topics = [topic("S1", IDENTICAL_A)]

        results, coverage = match_course(target_topics, pooled_topics, topic_threshold=0.75)

        assert coverage == 100.0
        assert all(r["covered"] for r in results)


class TestPartialMatch:
    def test_some_targets_covered(self):
        target_topics = [topic("T1", IDENTICAL_A), topic("T2", ORTHOGONAL)]
        pooled_topics = [topic("S1", IDENTICAL_B)]  # only matches T1 well

        results, coverage = match_course(target_topics, pooled_topics, topic_threshold=0.75)

        assert coverage == 50.0
        assert results[0]["covered"] is True   # T1 vs S1 -> sim 1.0
        assert results[1]["covered"] is False  # T2 vs S1 -> sim 0.0

    def test_partial_similarity_below_threshold(self):
        # PARTIAL is ~0.707 similar to IDENTICAL_A — below a 0.75 threshold.
        target_topics = [topic("T1", IDENTICAL_A)]
        pooled_topics = [topic("S1", PARTIAL)]

        results, coverage = match_course(target_topics, pooled_topics, topic_threshold=0.75)

        assert coverage == 0.0
        assert results[0]["covered"] is False
        assert results[0]["similarity"] < 0.75

    def test_partial_similarity_above_lowered_threshold(self):
        # Same vectors, but a looser threshold should now count it as covered.
        target_topics = [topic("T1", IDENTICAL_A)]
        pooled_topics = [topic("S1", PARTIAL)]

        results, coverage = match_course(target_topics, pooled_topics, topic_threshold=0.6)

        assert coverage == 100.0
        assert results[0]["covered"] is True


class TestNoMatch:
    def test_no_targets_covered(self):
        target_topics = [topic("T1", IDENTICAL_A), topic("T2", IDENTICAL_B)]
        pooled_topics = [topic("S1", ORTHOGONAL)]

        results, coverage = match_course(target_topics, pooled_topics, topic_threshold=0.75)

        assert coverage == 0.0
        assert all(not r["covered"] for r in results)

    def test_empty_pooled_topics(self):
        # Empty transcript / zero submitted topics case.
        target_topics = [topic("T1", IDENTICAL_A)]
        pooled_topics = []

        results, coverage = match_course(target_topics, pooled_topics)

        assert coverage == 0.0
        assert results[0]["covered"] is False
        assert results[0]["best_match_text"] is None
        assert results[0]["similarity"] == 0.0


class TestBestMatchSelection:
    def test_picks_highest_similarity_among_multiple_sources(self):
        target_topics = [topic("T1", IDENTICAL_A)]
        pooled_topics = [
            topic("Weak match", ORTHOGONAL),
            topic("Strong match", IDENTICAL_B),
            topic("Medium match", PARTIAL),
        ]

        results, coverage = match_course(target_topics, pooled_topics, topic_threshold=0.75)

        assert results[0]["best_match_text"] == "Strong match"
        assert results[0]["similarity"] == pytest.approx(1.0)


class TestInvalidInput:
    def test_empty_target_topics_raises(self):
        with pytest.raises(ValueError):
            match_course([], [topic("S1", IDENTICAL_A)])


class TestCrossCourseAllocation:
    def test_no_double_counting_higher_similarity_wins(self):
        """
        THE key test: one source topic that matches two different target
        courses' topics should only be allocated to ONE of them — the
        higher-similarity claim — not both.
        """
        # One shared source topic, similar to IDENTICAL_A's direction.
        shared_source = topic("Classification algorithms and decision trees", IDENTICAL_A)

        # Course 1 (ML): its target topic is an exact direction match -> sim 1.0
        ml_course = {
            "course_id": "ML101",
            "target_topics": [topic("Unit 2: Classification", IDENTICAL_A)],
        }
        # Course 2 (Data Mining): its target topic is close but not identical
        # (PARTIAL ~ 0.707 similarity to IDENTICAL_A) -> weaker claim on the
        # same source topic.
        dm_course = {
            "course_id": "DM101",
            "target_topics": [topic("Unit 4: Decision trees", PARTIAL)],
        }

        results = allocate_across_courses(
            [ml_course, dm_course],
            pooled_topics=[shared_source],
            topic_threshold=0.6,  # low enough that both WOULD match independently
        )

        ml_results, ml_coverage = results["ML101"]
        dm_results, dm_coverage = results["DM101"]

        # ML had the stronger claim (sim 1.0 vs ~0.707) -> it wins the source topic.
        assert ml_results[0]["covered"] is True
        assert ml_coverage == 100.0

        # DM's claim was weaker AND the source topic is now spent -> uncovered,
        # even though in isolation (via match_course()) it would have matched.
        assert dm_results[0]["covered"] is False
        assert dm_results[0]["best_match_text"] is None
        assert dm_coverage == 0.0

    def test_proves_isolated_match_course_would_double_count(self):
        """
        Sanity check on the bug itself: confirms match_course() run
        separately WOULD have double-counted the same source topic,
        which is exactly the scenario allocate_across_courses() fixes.
        """
        shared_source = topic("Classification algorithms and decision trees", IDENTICAL_A)

        ml_target = [topic("Unit 2: Classification", IDENTICAL_A)]
        dm_target = [topic("Unit 4: Decision trees", PARTIAL)]

        _, ml_coverage_isolated = match_course(ml_target, [shared_source], topic_threshold=0.6)
        _, dm_coverage_isolated = match_course(dm_target, [shared_source], topic_threshold=0.6)

        # Both would independently claim 100% coverage from the SAME source
        # topic if evaluated in isolation — this is the double-count bug.
        assert ml_coverage_isolated == 100.0
        assert dm_coverage_isolated == 100.0

    def test_enough_distinct_sources_both_courses_covered(self):
        """When there's a distinct source topic for each target, no
        conflict arises and both courses should be fully covered."""
        ml_course = {
            "course_id": "ML101",
            "target_topics": [topic("Unit 2: Classification", IDENTICAL_A)],
        }
        dm_course = {
            "course_id": "DM101",
            "target_topics": [topic("Unit 4: Decision trees", ORTHOGONAL)],
        }
        pooled = [
            topic("Source for ML", IDENTICAL_B),   # matches ML only
            topic("Source for DM", ORTHOGONAL),     # matches DM only
        ]

        results = allocate_across_courses([ml_course, dm_course], pooled, topic_threshold=0.75)

        assert results["ML101"][1] == 100.0
        assert results["DM101"][1] == 100.0

    def test_empty_courses_raises(self):
        with pytest.raises(ValueError):
            allocate_across_courses([], [topic("S1", IDENTICAL_A)])

    def test_no_pooled_topics_leaves_everything_uncovered(self):
        course = {"course_id": "C1", "target_topics": [topic("T1", IDENTICAL_A)]}
        results = allocate_across_courses([course], pooled_topics=[])

        per_topic_results, coverage = results["C1"]
        assert coverage == 0.0
        assert per_topic_results[0]["covered"] is False
