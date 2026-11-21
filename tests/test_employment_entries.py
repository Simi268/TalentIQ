import pytest

from app.resume_intelligence import extract_resume_intelligence


def get_entries(resume_text):
    result = extract_resume_intelligence(resume_text)
    return result["experience"]["employment_entries"]


def test_extracts_job_title_company_and_dates():
    resume = """
    EXPERIENCE
    Software Engineer | ABC Technologies
    Jan 2023 - Dec 2024
    Developed REST APIs using Python and FastAPI.
    Built backend services using PostgreSQL.
    """

    entries = get_entries(resume)

    assert len(entries) == 1

    entry = entries[0]

    assert entry["job_title"] == "Software Engineer"
    assert entry["company"] == "ABC Technologies"
    assert entry["start_date"] == "Jan 2023"
    assert entry["end_date"] == "Dec 2024"
    assert "python" in entry["technologies"]
    assert "fastapi" in entry["technologies"]
    assert len(entry["responsibilities"]) >= 1


def test_classifies_internship_correctly():
    resume = """
    INTERNSHIPS
    Machine Learning Intern | XYZ Labs
    Jun 2024 - Aug 2024
    Developed machine learning models using Python.
    """

    entries = get_entries(resume)

    assert len(entries) == 1
    assert entries[0]["employment_type"] == "internship"
    assert entries[0]["job_title"] == "Machine Learning Intern"
    assert entries[0]["company"] == "XYZ Labs"


def test_extracts_multiple_employment_entries():
    resume = """
    EXPERIENCE
    Software Engineer | ABC Technologies
    Jan 2022 - Dec 2023
    Developed REST APIs using Python and FastAPI.

    Data Analyst | XYZ Solutions
    Jan 2024 - Present
    Created dashboards using SQL and Tableau.
    """

    entries = get_entries(resume)

    assert len(entries) == 2

    assert entries[0]["job_title"] == "Software Engineer"
    assert entries[0]["company"] == "ABC Technologies"

    assert entries[1]["job_title"] == "Data Analyst"
    assert entries[1]["company"] == "XYZ Solutions"


def test_does_not_extract_projects_as_employment():
    resume = """
    PROJECTS
    Machine Learning Project
    Jan 2023 - Dec 2023
    Built a prediction model using Python.

    EDUCATION
    Bachelor of Technology
    2022 - 2026
    """

    entries = get_entries(resume)

    assert entries == []


def test_does_not_invent_employment_type():
    resume = """
    EXPERIENCE
    Backend Developer | ABC Technologies
    Jan 2023 - Dec 2024
    Developed APIs using Python.
    """

    entries = get_entries(resume)

    assert len(entries) == 1
    assert entries[0]["employment_type"] == "unknown"


def test_extracts_numeric_date_formats():
    resume = """
    EXPERIENCE
    Python Developer | ABC Technologies
    01/2023 - 12/2024
    Developed backend applications using Python.
    """

    entries = get_entries(resume)

    assert len(entries) == 1
    assert entries[0]["start_date"] == "01/2023"
    assert entries[0]["end_date"] == "12/2024"


def test_empty_experience_returns_empty_entries():
    resume = """
    EDUCATION
    Bachelor of Technology

    PROJECTS
    Resume Analyzer using Python.
    """

    entries = get_entries(resume)

    assert entries == []


def test_employment_evidence_is_preserved():
    resume = """
    EXPERIENCE
    Data Analyst | ABC Technologies
    Jan 2023 - Dec 2024
    Analyzed business data using SQL.
    Created reports using Tableau.
    """

    entries = get_entries(resume)

    assert len(entries) == 1

    evidence = " ".join(entries[0]["evidence"])

    assert "Analyzed business data using SQL." in evidence
    assert "Created reports using Tableau." in evidence