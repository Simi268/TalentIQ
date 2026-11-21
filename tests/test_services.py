import app.services as services



def test_skill_normalization_aliases():
    assert set(
        services.normalize_skills(
            "ML, NLP, Postgre SQL and Python"
        )
    ) >= {
        "machine learning",
        "natural language processing",
        "postgresql",
        "python"
    }


def test_jd_classifies_required_and_preferred():
    jd = services.analyze_jd(
        "Role: ML Engineer\n"
        "Must have Python and SQL. "
        "NLP is preferred. 3 years experience"
    )

    assert "python" in jd["required_skills"]
    assert "sql" in jd["required_skills"]

    assert (
        "natural language processing"
        in jd["preferred_skills"]
    )

    assert jd["minimum_experience"] == 3


def test_extraction_does_not_fabricate_contact():
    profile = services.extract_resume(
        "Avery Example\n"
        "Projects\n"
        "Built a Python NLP classifier"
    )

    assert profile["name"] == "Avery Example"
    assert profile["email"] is None
    assert profile["total_experience_years"] == 0


def test_score_explainable_and_capped(monkeypatch):

    # Mock semantic similarity to make scoring deterministic.
    monkeypatch.setattr(
        services,
        "semantic_similarity",
        lambda requirement, evidence: 0.40
    )

    jd = {
        "required_skills": ["python", "sql"],
        "preferred_skills": ["docker"],
        "minimum_experience": 3,
        "responsibilities": [],
        "education": None
    }

    profile = {
        "skills": ["python", "docker"],
        "relevant_experience_years": 12,
        "experience_evidence": ["Built services"]
    }

    result = services.score_candidate(
        jd,
        profile,
        "Python Docker built services"
    )

    assert result["score"] == 67.5

    assert result["missing_skills"] == ["sql"]

    assert result["breakdown"]["experience"] == 100

    assert result["breakdown"]["semantic_relevance"] == 40


def test_similarity_empty_and_identical():

    assert services.semantic_similarity("", "abc") == 0

    assert (
        services.semantic_similarity(
            "python api",
            "python api"
        ) > 0
    )


def test_score_is_always_within_range(monkeypatch):

    monkeypatch.setattr(
        services,
        "semantic_similarity",
        lambda requirement, evidence: 0.5
    )

    jd = {
        "required_skills": ["python"],
        "preferred_skills": ["docker"],
        "minimum_experience": 2,
        "responsibilities": [],
        "education": None
    }

    profile = {
        "skills": ["python", "docker"],
        "relevant_experience_years": 5,
        "experience_evidence": ["Python development"]
    }

    result = services.score_candidate(
        jd,
        profile,
        "Python Docker development"
    )

    assert 0 <= result["score"] <= 100

def test_explain_complete_score_uses_actual_score():
    result = {
        "score": 100.0,
        "provisional_score": None,
        "score_status": "complete",
        "evidence_coverage": 100.0,
        "unevaluated_weight": 0.0,
    }

    explanation = services.explain(
        result,
        {"name": "Simi Kumari"}
    )

    assert "100.00%" in explanation["summary"]
    assert "Insufficient evidence" not in explanation["summary"]
    assert explanation["score_status"] == "complete"


def test_explain_partial_score_uses_provisional_score():
    result = {
        "score": 85.0,
        "provisional_score": 85.0,
        "score_status": "partial",
        "evidence_coverage": 80.0,
        "unevaluated_weight": 20.0,
    }

    explanation = services.explain(
        result,
        {"name": "Simi Kumari"}
    )

    assert "85.00%" in explanation["summary"]
    assert "Provisional" in explanation["summary"]


def test_explain_insufficient_evidence():
    result = {
        "score": None,
        "provisional_score": None,
        "score_status": "insufficient_evidence",
        "evidence_coverage": 0.0,
        "unevaluated_weight": 100.0,
    }

    explanation = services.explain(
        result,
        {"name": "Simi Kumari"}
    )

    assert "reliable match score could not be calculated" in explanation["summary"]