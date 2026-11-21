import pytest

from app.ranking_engine import (
    rank_candidates,
    filter_candidates,
    compare_candidates,
    generate_ranking_summary,
)


@pytest.fixture
def candidates():
    return [
        {
            "candidate_id": "C1",
            "name": "Aarav",
            "overall_score": 82,
            "skills": ["Python", "SQL", "Machine Learning"],
            "experience": 2,
            "education": "B.Tech",
        },
        {
            "candidate_id": "C2",
            "name": "Meera",
            "overall_score": 91,
            "skills": ["Python", "TensorFlow", "Deep Learning"],
            "experience": 1,
            "education": "B.Tech",
        },
        {
            "candidate_id": "C3",
            "name": "Rohan",
            "overall_score": 64,
            "skills": ["Java", "SQL"],
            "experience": 3,
            "education": "BCA",
        },
        {
            "candidate_id": "C4",
            "name": "Isha",
            "overall_score": 45,
            "skills": ["Python"],
            "experience": 0,
            "education": "B.Tech",
        },
    ]


# -------------------------
# RANKING TESTS
# -------------------------

def test_candidates_are_ranked_highest_first(candidates):
    result = rank_candidates(candidates)

    assert result[0]["name"] == "Meera"
    assert result[1]["name"] == "Aarav"
    assert result[2]["name"] == "Rohan"
    assert result[3]["name"] == "Isha"


def test_ranking_assigns_positions(candidates):
    result = rank_candidates(candidates)

    assert [item["rank"] for item in result] == [1, 2, 3, 4]


def test_top_n_returns_only_requested_candidates(candidates):
    result = rank_candidates(candidates, top_n=2)

    assert len(result) == 2
    assert result[0]["name"] == "Meera"


def test_minimum_score_filter_in_ranking(candidates):
    result = rank_candidates(candidates, min_score=80)

    assert len(result) == 2
    assert all(item["overall_score"] >= 80 for item in result)


def test_equal_scores_preserve_original_order():
    data = [
        {"name": "A", "score": 80},
        {"name": "B", "score": 80},
    ]

    result = rank_candidates(data)

    assert result[0]["name"] == "A"
    assert result[1]["name"] == "B"


def test_empty_candidate_list():
    assert rank_candidates([]) == []


def test_invalid_top_n_raises_error(candidates):
    with pytest.raises(ValueError):
        rank_candidates(candidates, top_n=0)


def test_unscored_candidate_is_supported():
    candidates = [
        {"name": "Unscored Candidate"},
        {"name": "Scored Candidate", "overall_score": 75},
    ]

    result = rank_candidates(candidates)

    assert len(result) == 2
    assert result[0]["name"] == "Scored Candidate"
    assert result[1]["name"] == "Unscored Candidate"


# -------------------------
# FILTER TESTS
# -------------------------

def test_filter_by_minimum_score(candidates):
    result = filter_candidates(candidates, min_score=80)

    assert len(result) == 2


def test_filter_by_score_range(candidates):
    result = filter_candidates(
        candidates,
        min_score=60,
        max_score=85,
    )

    assert len(result) == 2
    assert all(60 <= item["overall_score"] <= 85 for item in result)


def test_filter_by_required_skills(candidates):
    result = filter_candidates(
        candidates,
        required_skills=["Python"],
    )

    assert len(result) == 3


def test_filter_by_multiple_required_skills(candidates):
    result = filter_candidates(
        candidates,
        required_skills=["Python", "SQL"],
    )

    assert len(result) == 1
    assert result[0]["name"] == "Aarav"


def test_filter_by_experience(candidates):
    result = filter_candidates(
        candidates,
        min_experience=2,
    )

    assert len(result) == 2


def test_unknown_experience_does_not_pass_threshold():
    data = [
        {"name": "A", "score": 90},
        {"name": "B", "score": 80, "experience": 2},
    ]

    result = filter_candidates(data, min_experience=1)

    assert len(result) == 1
    assert result[0]["name"] == "B"


def test_invalid_score_range_raises_error(candidates):
    with pytest.raises(ValueError):
        filter_candidates(
            candidates,
            min_score=90,
            max_score=50,
        )


# -------------------------
# COMPARISON TESTS
# -------------------------

def test_compare_candidates_returns_comparison(candidates):
    result = compare_candidates(candidates[:2])

    assert result["candidate_count"] == 2
    assert len(result["candidates"]) == 2


def test_comparison_sorts_by_score(candidates):
    result = compare_candidates(candidates[:2])

    assert result["candidates"][0]["name"] == "Meera"


def test_comparison_includes_requested_fields(candidates):
    result = compare_candidates(
        candidates[:2],
        fields=["overall_score", "education"],
    )

    assert "education" in result["candidates"][0]
    assert "skills" not in result["candidates"][0]


def test_comparison_requires_two_candidates(candidates):
    with pytest.raises(ValueError):
        compare_candidates(candidates[:1])


# -------------------------
# SUMMARY TESTS
# -------------------------

def test_ranking_summary_counts_candidates(candidates):
    result = generate_ranking_summary(candidates)

    assert result["total_candidates"] == 4


def test_ranking_summary_calculates_average(candidates):
    result = generate_ranking_summary(candidates)

    assert result["average_score"] == 70.5


def test_ranking_summary_identifies_top_candidate(candidates):
    result = generate_ranking_summary(candidates)

    assert result["top_candidate"]["name"] == "Meera"
    assert result["top_candidate"]["score"] == 91


def test_ranking_summary_calculates_distribution(candidates):
    result = generate_ranking_summary(candidates)

    assert result["score_distribution"] == {
    "90-100": 1,
    "80-89": 1,
    "70-79": 0,
    "60-69": 1,
    "below-60": 1,
    "unscored": 0,
}


def test_empty_ranking_summary():
    result = generate_ranking_summary([])

    assert result["total_candidates"] == 0
    assert result["top_candidate"] is None