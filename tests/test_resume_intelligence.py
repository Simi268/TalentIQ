from datetime import date

import pytest

from app.resume_intelligence import (
    extract_resume_intelligence,
    split_sections,
)


SAMPLE = """Avery Stone
avery@example.com
+1 415 555 0134

SUMMARY
Software engineer with 4 years of professional experience.

SKILLS
Python, FastAPI, PostgreSQL, Docker, NLP

EXPERIENCE
Software Engineer | Acme
Jan 2022 - Dec 2024
Built REST APIs using Python and FastAPI.

INTERNSHIPS
ML Intern | Lab
Jun 2021 - Aug 2021
Worked on NLP prototypes.

EDUCATION
Bachelor of Computer Science

PROJECTS
Resume matcher using Python and NLP.
"""


def test_extracts_contact_and_candidate_name():
    result = extract_resume_intelligence(SAMPLE, date(2025, 1, 1))
    assert result["candidate"]["name"] == "Avery Stone"
    assert result["candidate"]["email"] == "avery@example.com"
    assert result["candidate"]["phone"] is not None


def test_skills_have_evidence_and_section():
    result = extract_resume_intelligence(SAMPLE, date(2025, 1, 1))
    skills = {item["name"]: item for item in result["skills"]}
    assert "python" in skills
    assert "skills" in skills["python"]["sections"]
    assert skills["python"]["evidence"]


def test_professional_and_internship_experience_are_separate():
    result = extract_resume_intelligence(SAMPLE, date(2025, 1, 1))
    exp = result["experience"]
    assert exp["professional_experience_years"] == 3.0
    assert exp["internship_experience_years"] == pytest.approx(0.25)
    assert exp["stated_experience_years"] == 4.0


def test_projects_are_not_counted_as_employment():
    result = extract_resume_intelligence(SAMPLE, date(2025, 1, 1))
    exp = result["experience"]
    assert exp["professional_experience_years"] == 3.0
    assert exp["project_evidence"]


def test_empty_resume_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        extract_resume_intelligence("   ")


def test_sections_are_detected():
    sections = split_sections(SAMPLE)
    assert "skills" in sections
    assert "experience" in sections
    assert "internships" in sections
    assert "education" in sections

def test_project_extraction_removes_link_labels():
    resume = """
    Avery Stone

    PROJECTS
    TalentIQ - Resume Intelligence Platform | GitHub | Live Demo
    https://github.com/example/talentiq
    GitHub
    Built a resume matching platform using Python.
    """

    result = extract_resume_intelligence(
        resume,
        date(2025, 1, 1)
    )

    projects = result["projects"]
    titles = [p["title"] for p in projects]
    descriptions = [p["description"] for p in projects]

    assert any("TalentIQ" in title for title in titles)
    assert any(
        "Built a resume matching platform" in description
        for description in descriptions
    )

    combined = str(projects).lower()

    assert "github | live demo" not in combined
    assert "github.com" not in combined


def test_project_extraction_preserves_real_project_titles():
    resume = """
    Avery Stone

    PROJECTS
    BeliefGraph
    Dependency-aware recovery for AI agents.
    MedIntel AI
    Healthcare assistant using retrieval augmented generation.
    """

    result = extract_resume_intelligence(
        resume,
        date(2025, 1, 1)
    )

    titles = [
        project["title"]
        for project in result["projects"]
    ]

    assert "BeliefGraph" in titles
    assert "MedIntel AI" in titles