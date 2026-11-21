import pytest

from app.scoring_engine import (
    calculate_skill_score,
    calculate_experience_score,
    calculate_education_score,
    calculate_weighted_score,
    score_candidate,
    validate_weights,
)


def test_exact_skill_score():

    results = [
        {"requirement": "python", "status": "exact_match"},
        {"requirement": "sql", "status": "exact_match"},
    ]

    result = calculate_skill_score(results)

    assert result["score"] == 100


def test_related_skill_score():

    results = [
        {"requirement": "nlp", "status": "related_match"},
    ]

    result = calculate_skill_score(results)

    assert result["score"] == 50


def test_unverified_skills_are_not_treated_as_confirmed_failure():

    results = [
        {"requirement": "python", "status": "exact_match"},
        {"requirement": "sql", "status": "unverified"},
    ]

    result = calculate_skill_score(results)

    assert result["score"] == 100

    assert result["coverage"] == 50


def test_all_skills_unverified():

    results = [
        {"requirement": "python", "status": "unverified"},
    ]

    result = calculate_skill_score(results)

    assert result["score"] is None

    assert result["coverage"] == 0


def test_experience_score():

    jd = {
        "minimum_experience": 3
    }

    profile = {
        "relevant_experience_years": 2
    }

    result = calculate_experience_score(
        jd,
        profile
    )

    assert result["score"] == pytest.approx(66.67)


def test_experience_score_is_capped():

    jd = {
        "minimum_experience": 3
    }

    profile = {
        "relevant_experience_years": 10
    }

    result = calculate_experience_score(
        jd,
        profile
    )

    assert result["score"] == 100


def test_missing_experience_is_unknown():

    jd = {
        "minimum_experience": 3
    }

    profile = {}

    result = calculate_experience_score(
        jd,
        profile
    )

    assert result["score"] is None

    assert result["status"] == "unverified"


def test_no_experience_requirement():

    result = calculate_experience_score(
        {},
        {}
    )

    assert result["score"] is None


def test_education_missing():

    jd = {
        "education": ["Bachelor of Computer Science"]
    }

    result = calculate_education_score(
        jd,
        {}
    )

    assert result["score"] is None

    assert result["status"] == "unverified"


def test_weights_sum_to_100():

    validate_weights()


def test_invalid_weights():

    with pytest.raises(ValueError):

        validate_weights({
            "required_skills": 50,
            "experience": 30
        })


def test_weighted_score():

    components = {

        "required_skills": {"score": 100},

        "semantic_relevance": {"score": 80},

        "experience": {"score": 100},

        "education": {"score": 100},

        "preferred_skills": {"score": 100},

    }

    result = calculate_weighted_score(
        components
    )

    assert result["score"] == 95

    assert result["evaluated_weight"] == 100


def test_missing_components_are_not_zero():

    components = {

        "required_skills": {"score": 100},

        "semantic_relevance": {"score": None},

        "experience": {"score": 100},

        "education": {"score": None},

        "preferred_skills": {"score": 100},

    }

    result = calculate_weighted_score(
        components
    )

    assert result["score"] == 100

    assert result["evaluated_weight"] == 65


def test_complete_candidate_scoring():

    jd = {

        "minimum_experience": 3,

        "education": None,

    }

    profile = {

        "relevant_experience_years": 3,

    }

    matching_result = {

        "required_skill_analysis": [

            {
                "requirement": "python",
                "status": "exact_match",
                "similarity": 1.0,
            },

            {
                "requirement": "sql",
                "status": "unverified",
                "similarity": 0.0,
            },

        ],

        "preferred_skill_analysis": [

            {
                "requirement": "docker",
                "status": "exact_match",
                "similarity": 1.0,
            }

        ]

    }

    result = score_candidate(
        jd,
        profile,
        matching_result
    )

    assert result["score"] is not None

    assert 0 <= result["score"] <= 100

    assert result["missing_skills"] == []
    assert result["unverified_skills"] == ["sql"]

    assert result["breakdown"]["experience"]["score"] == 100


def test_score_has_explanations():

    jd = {
        "minimum_experience": 2,
        "education": None,
    }

    profile = {
        "relevant_experience_years": 2,
    }

    matching_result = {
        "required_skill_analysis": [
            {
                "requirement": "python",
                "status": "exact_match",
                "similarity": 1.0,
            }
        ],
        "preferred_skill_analysis": [],
    }

    result = score_candidate(
        jd,
        profile,
        matching_result
    )

    assert len(result["explanations"]) > 0

    assert "required_skills" in result["breakdown"]

from app.scoring_engine import calculate_skill_score


def test_missing_required_skills_are_not_excluded():
    results = [
        {"requirement": "Python", "status": "exact_match"},
        {"requirement": "SQL", "status": "exact_match"},
        {"requirement": "Machine Learning", "status": "unverified"},
        {"requirement": "Deep Learning", "status": "unverified"},
        {"requirement": "NLP", "status": "unverified"},
        {"requirement": "TensorFlow", "status": "unverified"},
        {"requirement": "Scikit-learn", "status": "unverified"},
    ]

    result = calculate_skill_score(results)

    assert result["score"] == 100.0
    assert result["coverage_score"] == 28.57
    assert result["aggregation_score"] == 28.57
    assert result["evaluated"] == 2
    assert result["total"] == 7

def test_related_skills_receive_partial_credit():
    results = [
        {"requirement": "Python", "status": "exact_match"},
        {"requirement": "Machine Learning", "status": "related_match"},
        {"requirement": "Deep Learning", "status": "unverified"},
    ]

    result = calculate_skill_score(results)

    assert result["score"] == 75.0
    assert result["coverage_score"] == 50.0
    assert result["aggregation_score"] == 50.0
    assert result["evaluated"] == 2
    assert result["total"] == 3


def test_all_exact_skills_receive_full_credit():
    results = [
        {"requirement": "Python", "status": "exact_match"},
        {"requirement": "SQL", "status": "exact_match"},
    ]

    result = calculate_skill_score(results)

    assert result["score"] == 100.0