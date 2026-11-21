import pytest

from app.candidate_intelligence import (
    compare_candidates,
    explain_ranking,
    evaluate_ranking,
)


def test_compare_candidates_supports_flat_profiles():
    result = compare_candidates([
        {
            "id": 1,
            "name": "Avery",
            "score": 88,
            "skills": ["Python", "SQL"],
            "relevant_experience_years": 2,
        },
        {
            "id": 2,
            "name": "Jordan",
            "score": 76,
            "skills": ["Python", "Docker"],
            "relevant_experience_years": 1,
        },
    ])

    assert result["candidate_count"] == 2
    assert result["candidates"][0]["name"] == "Avery"
    assert result["candidates"][0]["score"] == 88
    assert result["candidates"][0]["experience_years"] == 2


def test_compare_candidates_supports_structured_skills():
    result = compare_candidates([{
        "id": "c1",
        "profile": {
            "name": "Taylor",
            "skills": [
                {"name": "python", "sections": ["skills"]},
                {"name": "sql", "sections": ["projects"]},
            ],
            "relevant_experience_years": None,
        },
        "score": 70,
    }])

    assert result["candidates"][0]["skills"] == ["python", "sql"]
    assert result["candidates"][0]["experience_years"] is None


def test_compare_candidates_filters_selected_ids():
    result = compare_candidates(
        [{"id": 1, "score": 90}, {"id": 2, "score": 80}],
        candidate_ids=[2],
    )
    assert result["candidate_count"] == 1
    assert result["candidates"][0]["candidate_id"] == 2


def test_compare_candidates_reports_unknown_ids():
    result = compare_candidates(
        [{"id": 1, "score": 90}],
        candidate_ids=[1, 9],
    )
    assert result["missing_candidate_ids"] == [9]


def test_compare_candidates_builds_skill_matrix():
    result = compare_candidates([
        {"id": 1, "skills": ["python"]},
        {"id": 2, "skills": ["sql"]},
    ])
    matrix = {row["skill"]: row["candidates"] for row in result["skill_matrix"]}
    assert matrix["python"] == {1: True, 2: False}
    assert matrix["sql"] == {1: False, 2: True}


def test_compare_candidates_handles_empty_input():
    result = compare_candidates([])
    assert result["candidate_count"] == 0
    assert result["candidates"] == []


def test_compare_candidates_rejects_non_list():
    with pytest.raises(TypeError):
        compare_candidates({})


def test_compare_candidates_reads_legacy_explanation():
    result = compare_candidates([{
        "id": 3,
        "score": 80,
        "explanation": {
            "satisfied": ["python"],
            "not_verified": ["sql"],
            "related_skills": ["pytorch"],
        },
    }])
    evidence = result["candidates"][0]["evidence"]
    assert evidence["matched"] == ["python"]
    assert evidence["missing"] == ["sql"]
    assert evidence["related"] == ["pytorch"]


def test_explain_ranking_orders_by_score_and_reports_gap():
    result = explain_ranking([
        {"id": 1, "name": "A", "score": 70},
        {"id": 2, "name": "B", "score": 90},
        {"id": 3, "name": "C", "score": 60},
    ])
    assert [item["name"] for item in result] == ["B", "A", "C"]
    assert result[0]["rank"] == 1
    assert result[1]["score_gap_to_previous"] == 20
    assert result[2]["score_gap_to_previous"] == 10


def test_explain_ranking_includes_component_scores_and_evidence():
    result = explain_ranking([{
        "id": "x",
        "name": "Morgan",
        "score": 82,
        "breakdown": {"skills": {"score": 90}, "experience": 70},
        "explanation": {"satisfied": ["python"], "not_verified": ["sql"]},
    }])
    assert result[0]["component_scores"] == {
        "skills": 90,
        "experience": 70,
    }
    assert result[0]["evidence_summary"]["matched"] == 1


def test_evaluate_ranking_perfect_order():
    result = evaluate_ranking(
        ["a", "b", "c"],
        {"a", "b"},
        k=3,
    )
    assert result["evaluated"] is True
    assert result["precision_at_k"] == pytest.approx(2 / 3, abs=0.0001)
    assert result["recall_at_k"] == 1
    assert result["reciprocal_rank"] == 1
    assert result["average_precision"] == 1
    assert result["ndcg_at_k"] == 1


def test_evaluate_ranking_partial_recall():
    result = evaluate_ranking(
        ["x", "a", "y"],
        {"a", "b"},
        k=3,
    )
    assert result["precision_at_k"] == pytest.approx(1 / 3, abs=0.0001)
    assert result["recall_at_k"] == 0.5
    assert result["reciprocal_rank"] == 0.5


def test_evaluate_ranking_returns_unscored_when_labels_missing():
    result = evaluate_ranking(["a", "b"], set())
    assert result["evaluated"] is False
    assert result["ndcg_at_k"] is None


def test_evaluate_ranking_validates_k():
    with pytest.raises(ValueError):
        evaluate_ranking(["a"], {"a"}, k=0)


def test_evaluate_ranking_handles_empty_ranking():
    result = evaluate_ranking([], {"a"})
    assert result["evaluated"] is True
    assert result["precision_at_k"] == 0
    assert result["recall_at_k"] == 0
