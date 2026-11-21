from app.llm_service import extract_jd_with_llm


def test_groq_structured_jd_extraction():
    jd = """
    AI/ML Engineer Intern

    Must have Python and SQL.
    PyTorch is preferred.
    0-1 years of experience.
    Bachelor's degree in Computer Science.

    Responsibilities:
    Develop machine learning models.
    Build NLP applications.
    """

    result = extract_jd_with_llm(jd)

    assert result["job_title"]
    assert "python" in [
        skill.lower() for skill in result["required_skills"]
    ]
    assert result["experience"]["minimum"] == 0
    assert result["experience"]["maximum"] == 1
    assert result["education"]
    assert result["responsibilities"]