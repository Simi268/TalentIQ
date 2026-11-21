import pytest

from app.jd_intelligence import (
    analyze_jd,
    extract_skills,
    extract_experience,
    extract_job_title,
)


SAMPLE_JD = """
AI/ML Engineer

Job Title: AI/ML Engineer

Requirements:

Must have strong proficiency in Python and SQL.

Machine Learning and NLP are required.

PyTorch and TensorFlow are preferred.

Docker is nice to have.

Minimum 2 years of experience in AI development.

Bachelor's degree in Computer Science or Engineering.

Responsibilities:

Develop machine learning models.

Build and deploy NLP applications.

Optimize model performance.

AWS certification is desirable.
"""


def test_job_title_extraction():

    result = extract_job_title(SAMPLE_JD)

    assert result == "AI/ML Engineer"


def test_mandatory_skill_extraction():

    result = analyze_jd(SAMPLE_JD)

    assert "python" in result["required_skills"]

    assert "sql" in result["required_skills"]


def test_preferred_skill_extraction():

    result = analyze_jd(SAMPLE_JD)

    assert "pytorch" in result["preferred_skills"]

    assert "tensorflow" in result["preferred_skills"]

    assert "docker" in result["preferred_skills"]


def test_experience_extraction():

    result = extract_experience(SAMPLE_JD)

    assert result["minimum_experience"] == 2


def test_education_extraction():

    result = analyze_jd(SAMPLE_JD)

    assert any(
        "computer science" in item.lower()
        for item in result["education"]
    )


def test_responsibility_extraction():

    result = analyze_jd(SAMPLE_JD)

    assert any(
        "machine learning models" in item.lower()
        for item in result["responsibilities"]
    )


def test_certification_extraction():

    result = analyze_jd(SAMPLE_JD)

    assert any(
        "aws certification" in item.lower()
        for item in result["certifications"]
    )


def test_skill_evidence_is_preserved():

    result = analyze_jd(SAMPLE_JD)

    assert "python" in result["skill_evidence"]

    assert result["skill_evidence"]["python"]["evidence_sentences"]


def test_metadata_counts():

    result = analyze_jd(SAMPLE_JD)

    assert result["metadata"]["total_skills"] > 0

    assert result["metadata"]["mandatory_skill_count"] > 0


def test_empty_jd():

    with pytest.raises(ValueError):

        analyze_jd("")


def test_unclassified_skills_are_preserved():

    result = extract_skills(
        "The candidate should know Python and PostgreSQL."
    )

    assert "python" in result["unclassified_skills"]

    assert "postgresql" in result["unclassified_skills"]

def test_skill_extraction_with_punctuation():

    result = extract_skills(
        "Must have Python, SQL, PostgreSQL, and Docker."
    )

    assert "python" in result["required_skills"]
    assert "sql" in result["required_skills"]
    assert "postgresql" in result["required_skills"]
    assert "docker" in result["required_skills"]