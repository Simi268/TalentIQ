"""
TalentIQ Resume Intelligence Engine
-----------------------------------
Extracts structured, evidence-backed information from resume text.

This module deliberately does NOT infer or fabricate facts. It distinguishes:
- skills explicitly found in text
- the section in which each skill appears
- professional experience evidence
- internship evidence
- project evidence
- total experience stated explicitly by the candidate

Date-range calculation is intentionally conservative. It only calculates durations
when a recognizable date range is present in an Experience/Employment section.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any


# Canonical skill -> accepted textual aliases.
# Extend this taxonomy as the product grows. Related skills are NOT treated as equal.
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "python": ("python",),
    "java": ("java",),
    "javascript": ("javascript", "js"),
    "typescript": ("typescript", "ts"),
    "c++": ("c++",),
    "c#": ("c#", "c sharp"),
    "sql": ("sql",),
    "postgresql": ("postgresql", "postgres", "postgre sql"),
    "mysql": ("mysql",),
    "mongodb": ("mongodb", "mongo db"),
    "fastapi": ("fastapi",),
    "flask": ("flask",),
    "django": ("django",),
    "react": ("react", "react.js"),
    "node.js": ("node.js", "nodejs"),
    "html": ("html", "html5"),
    "css": ("css", "css3"),
    "machine learning": ("machine learning", "ml"),
    "deep learning": ("deep learning",),
    "natural language processing": ("natural language processing", "nlp"),
    "computer vision": ("computer vision",),
    "generative ai": ("generative ai", "genai", "gen ai"),
    "large language models": ("large language models", "llm", "llms"),
    "retrieval augmented generation": ("retrieval augmented generation", "rag"),
    "transformers": ("transformers", "transformer architecture"),
    "pytorch": ("pytorch",),
    "tensorflow": ("tensorflow",),
    "keras": ("keras",),
    "scikit-learn": ("scikit-learn", "sklearn", "scikit learn"),
    "pandas": ("pandas",),
    "numpy": ("numpy",),
    "spacy": ("spacy", "spaCy"),
    "hugging face": ("hugging face", "huggingface"),
    "langchain": ("langchain",),
    "llamaindex": ("llamaindex", "llama index"),
    "chromadb": ("chromadb", "chroma db"),
    "faiss": ("faiss",),
    "docker": ("docker",),
    "kubernetes": ("kubernetes", "k8s"),
    "aws": ("amazon web services", "aws"),
    "azure": ("microsoft azure", "azure"),
    "gcp": ("google cloud platform", "gcp"),
    "git": ("git",),
    "github": ("github",),
    "linux": ("linux",),
    "rest api": ("rest api", "restful api", "rest apis"),
    "graphql": ("graphql",),
    "pytest": ("pytest",),
    "agile": ("agile",),
    "scrum": ("scrum",),

    # Business Analysis
    "business analysis": ("business analysis", "business analyst"),
    "requirements gathering": ("requirements gathering", "requirement gathering"),
    "requirement analysis": ("requirement analysis", "requirements analysis"),
    "business requirements": ("business requirements", "business requirement"),
    "functional requirements": ("functional requirements",),
    "technical documentation": ("technical documentation",),
    "user stories": ("user stories", "user story"),
    "acceptance criteria": ("acceptance criteria",),
    "use cases": ("use cases", "use case"),
    "process mapping": ("process mapping",),
    "gap analysis": ("gap analysis",),
    "stakeholder management": ("stakeholder management",),
    "stakeholder communication": ("stakeholder communication",),
    "data analysis": ("data analysis",),
    "data visualization": ("data visualization",),
    "microsoft excel": ("microsoft excel", "ms excel"),
    "power bi": ("power bi", "powerbi"),
    "tableau": ("tableau",),
    "vlookup": ("vlookup", "v-lookup"),
    "pivot tables": ("pivot tables", "pivot table"),
    "jira": ("jira",),
    "confluence": ("confluence",),
    "agile methodology": ("agile methodology",),
    "waterfall methodology": ("waterfall methodology",),
    "uml": ("uml",),
    "bpmn": ("bpmn",),
    "sql reporting": ("sql reporting",),
    "kpi reporting": ("kpi reporting", "kpi analysis"),
        # Human Resources & Recruitment
    "human resource management": (
        "human resource management", "hr management", "hrm"
    ),
    "talent acquisition": (
        "talent acquisition", "talent acquisition executive"
    ),
    "recruitment coordination": (
        "recruitment coordination", "recruitment coordinator"
    ),
    "resume screening": (
        "resume screening", "cv screening", "curriculum vitae screening"
    ),
    "candidate evaluation": (
        "candidate evaluation", "candidate assessment"
    ),
    "applicant tracking system": (
        "applicant tracking system", "applicant tracking systems",
        "ats"
    ),
    "interview scheduling": (
        "interview scheduling", "interview coordination",
        "interview scheduling and coordination"
    ),
    "candidate relationship management": (
        "candidate relationship management", "candidate engagement"
    ),
    "candidate sourcing": (
        "candidate sourcing", "talent sourcing", "sourcing profiles"
    ),
    "onboarding": (
        "onboarding", "employee onboarding", "onboarding documentation"
    ),
    "recruitment reporting": (
        "recruitment reporting", "hiring reports", "recruitment reports"
    ),
    "recruitment metrics": (
        "recruitment metrics", "hiring metrics"
    ),
    "recruitment mis": (
        "recruitment mis", "recruitment management information system"
    ),
    "hr operations": (
        "hr operations", "human resources operations"
    ),
    "hr documentation": (
        "hr documentation", "employee documentation"
    ),
    "employee lifecycle management": (
        "employee lifecycle", "employee lifecycle management"
    ),
    "stakeholder communication": (
        "stakeholder communication", "communication with stakeholders"
    ),
    "candidate communication": (
        "candidate communication", "candidate follow-ups",
        "candidate reminders"
    ),
    "interpersonal skills": (
        "interpersonal skills", "people skills"
    ),
    "teamwork": (
        "teamwork", "team collaboration", "collaboration"
    ),
    "attention to detail": (
        "attention to detail", "detail-oriented"
    ),
    "time management": (
        "time management", "time-management"
    ),
    "problem solving": (
        "problem solving", "problem-solving"
    ),
    "multitasking": (
        "multitasking", "multiple responsibilities"
    ),
    "verbal communication": (
        "verbal communication", "verbal and written communication"
    ),
    "written communication": (
        "written communication", "business writing"
    ),
    "google workspace": (
        "google workspace", "google sheets", "google docs"
    ),
}

SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "profile", "objective", "career objective"),
    "skills": ("skills", "technical skills", "core skills", "key skills", "technical expertise"),
    "experience": ("experience", "work experience", "professional experience",
                   "employment history", "work history", "professional background"),
    "internships": ("internship", "internships", "internship experience"),
    "education": ("education", "academic background", "qualifications", "educational background"),
    "projects": ("projects", "personal projects", "academic projects", "project experience"),
    "certifications": ("certifications", "certificates", "licenses and certifications"),
    "achievements": ("achievements", "awards", "accomplishments"),
}

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" \t•|-–")


def _section_key(line: str) -> str | None:
    normalized = re.sub(r"[^a-z ]", "", line.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    for key, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return key
    return None


def split_sections(text: str) -> dict[str, list[str]]:
    """Split resume into known sections while retaining unclassified text."""
    sections: dict[str, list[str]] = defaultdict(list)
    current = "general"

    for raw in text.replace("\r", "\n").splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        key = _section_key(line.rstrip(":"))
        if key:
            current = key
            continue
        sections[current].append(line)

    return dict(sections)


def _find_skill_mentions(text: str, sections: dict[str, list[str]]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for section, lines in sections.items():
        section_text = "\n".join(lines)
        lower_text = section_text.lower()

        for canonical, aliases in SKILL_ALIASES.items():
            for alias in aliases:
                # Avoid unreliable short aliases.
                if len(alias) <= 2 and alias.lower() not in {
                    "c#", "c++"
                }:
                    continue

                pattern = (
                    r"(?<![a-z0-9+#.])"
                    + re.escape(alias.lower())
                    + r"(?![a-z0-9+#.])"
                )

                match = re.search(pattern, lower_text)

                if match:
                    evidence_line = next(
                        (
                            ln for ln in lines
                            if re.search(pattern, ln.lower())
                        ),
                        None,
                    )

                    item = found.setdefault(
                        canonical,
                        {
                            "name": canonical,
                            "sections": [],
                            "evidence": [],
                        },
                    )

                    if section not in item["sections"]:
                        item["sections"].append(section)

                    if evidence_line and evidence_line not in item["evidence"]:
                        item["evidence"].append(evidence_line)

                    break

    return sorted(found.values(), key=lambda x: x["name"])


def _parse_month_year(
    value: str,
    current_date: date,
) -> tuple[int, int] | None:
    """Parse month-year, numeric month-year, or year-only dates."""

    value = value.strip().lower().replace(".", "")

    if value in {"present", "current", "now"}:
        return current_date.year, current_date.month

    # January 2023 / Jan 2023
    match = re.fullmatch(
        r"([a-z]{3,9})\s+((?:19|20)\d{2})",
        value,
    )

    if match and match.group(1) in MONTHS:
        return int(match.group(2)), MONTHS[match.group(1)]

    # 01/2023 or 01-2023
    match = re.fullmatch(
        r"(0?[1-9]|1[0-2])[/\-]((?:19|20)\d{2})",
        value,
    )

    if match:
        return int(match.group(2)), int(match.group(1))

    # 2023
    match = re.fullmatch(r"((?:19|20)\d{2})", value)

    if match:
        return int(match.group(1)), 1

    return None

def _date_range_from_line(
    line: str,
    current_date: date,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Extract a valid date range from a line."""

    date_token = (
        r"(?:"
        r"[A-Za-z]{3,9}\.?\s+(?:19|20)\d{2}"
        r"|"
        r"(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}"
        r"|"
        r"(?:19|20)\d{2}"
        r"|"
        r"Present|Current|Now"
        r")"
    )

    pattern = re.compile(
        rf"(?P<start>{date_token})"
        rf"\s*(?:-|–|—|\bto\b)\s*"
        rf"(?P<end>{date_token})",
        re.IGNORECASE,
    )

    match = pattern.search(line)

    if not match:
        return None

    start = _parse_month_year(
        match.group("start"),
        current_date,
    )

    end = _parse_month_year(
        match.group("end"),
        current_date,
    )

    if not start or not end:
        return None

    start_index = start[0] * 12 + start[1]
    end_index = end[0] * 12 + end[1]

    if end_index < start_index:
        return None

    if end_index - start_index > 600:
        return None

    return start, end

def _is_probable_employment_entry(
    lines: list[str],
    index: int,
) -> bool:
    """Check whether a date range is associated with an employment entry."""

    line = lines[index].strip()

    # Reject ordinary achievement/project bullet points.
    if re.match(
        r"^[•\-*]\s*(built|developed|created|implemented|"
        r"designed|worked|managed|analyzed|analysed|"
        r"improved|deployed|used|performed)\b",
        line,
        re.IGNORECASE,
    ):
        return False

    # Reject obvious educational and project date descriptions.
    reject_pattern = re.compile(
        r"\b("
        r"graduated|graduation|coursework|"
        r"academic project|personal project|"
        r"project duration|semester|"
        r"expected graduation"
        r")\b",
        re.IGNORECASE,
    )

    if reject_pattern.search(line):
        return False

    # Inspect nearby lines for employment-related evidence.
    start = max(0, index - 2)
    end = min(len(lines), index + 3)

    context = " ".join(lines[start:end])

    employment_pattern = re.compile(
        r"\b("
        r"intern|internship|trainee|"
        r"engineer|developer|analyst|"
        r"manager|consultant|designer|"
        r"associate|specialist|"
        r"executive|administrator|"
        r"officer|lead|director|"
        r"employee|employment|"
        r"worked at|working at|"
        r"company|organization|organisation"
        r")\b",
        re.IGNORECASE,
    )

    return bool(employment_pattern.search(context))

def _extract_employment_intervals(
    lines: list[str],
    current_date: date,
) -> tuple[
    list[tuple[tuple[int, int], tuple[int, int]]],
    list[tuple[tuple[int, int], tuple[int, int]]],
    list[str],
    list[str],
    list[str],
]:
    """Extract professional and internship employment intervals."""

    professional_intervals = []
    internship_intervals = []

    professional_evidence = []
    internship_evidence = []
    ambiguous_evidence = []

    internship_pattern = re.compile(
        r"\b(intern|internship|trainee|student intern)\b",
        re.IGNORECASE,
    )

    for index, line in enumerate(lines):

        date_range = _date_range_from_line(
            line,
            current_date,
        )

        if not date_range:
            continue

        if not _is_probable_employment_entry(lines, index):
            ambiguous_evidence.append(line)
            continue

        start = max(0, index - 2)
        end = min(len(lines), index + 3)

        context_lines = lines[start:end]
        context = " ".join(context_lines)

        if internship_pattern.search(context):

            internship_intervals.append(date_range)

            internship_evidence.extend(context_lines)

        else:

            professional_intervals.append(date_range)

            professional_evidence.extend(context_lines)

    return (
        professional_intervals,
        internship_intervals,
        list(dict.fromkeys(professional_evidence)),
        list(dict.fromkeys(internship_evidence)),
        list(dict.fromkeys(ambiguous_evidence)),
    )


def _duration_from_range(line: str, current_date: date) -> float | None:
    """Return duration in years for a recognizable date range; otherwise None."""
    date_token = r"(?:[A-Za-z]{3,9}\.?\s+)?(?:19|20)\d{2}|Present|Current|Now"
    pattern = re.compile(
        rf"(?P<start>{date_token})\s*(?:-|–|—|to)\s*(?P<end>{date_token})",
        re.IGNORECASE,
    )
    match = pattern.search(line)
    if not match:
        return None

    start = _parse_month_year(match.group("start"), current_date)
    end = _parse_month_year(match.group("end"), current_date)
    if not start or not end:
        return None

    months = (end[0] - start[0]) * 12 + (end[1] - start[1]) + 1
    if months <= 0 or months > 12 * 50:
        return None
    return round(months / 12, 2)

def _date_range_from_line(
    line: str,
    current_date: date,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Extract date ranges in textual, numeric or year-only formats."""

    date_token = (
        r"(?:"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
        r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\.?\s+(?:19|20)\d{2}"
        r"|"
        r"(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}"
        r"|"
        r"(?:19|20)\d{2}"
        r"|"
        r"Present|Current|Now"
        r")"
    )

    pattern = re.compile(
        rf"(?<!\w)(?P<start>{date_token})"
        rf"\s*(?:-|–|—|\bto\b)\s*"
        rf"(?P<end>{date_token})(?!\w)",
        re.IGNORECASE,
    )

    match = pattern.search(line)

    if not match:
        return None

    start = _parse_month_year(match.group("start"), current_date)
    end = _parse_month_year(match.group("end"), current_date)

    if not start or not end:
        return None

    start_index = start[0] * 12 + start[1]
    end_index = end[0] * 12 + end[1]

    if end_index < start_index:
        return None

    if end_index - start_index > 600:
        return None

    return start, end

def _calculate_cumulative_experience(
    intervals: list[
        tuple[tuple[int, int], tuple[int, int]]
    ],
) -> float | None:
    """Calculate cumulative experience without double-counting overlaps."""

    if not intervals:
        return None

    month_intervals = []

    for start, end in intervals:

        start_month = start[0] * 12 + start[1]
        end_month = end[0] * 12 + end[1]

        if end_month < start_month:
            continue

        month_intervals.append(
            (start_month, end_month)
        )

    if not month_intervals:
        return None

    month_intervals.sort()

    merged = []

    current_start, current_end = month_intervals[0]

    for start, end in month_intervals[1:]:

        if start <= current_end + 1:
            current_end = max(current_end, end)

        else:
            merged.append(
                (current_start, current_end)
            )

            current_start, current_end = start, end

    merged.append(
        (current_start, current_end)
    )

    total_months = sum(
        end - start + 1
        for start, end in merged
    )

    return round(total_months / 12, 2)


def _clean_project_lines(lines: list[str]) -> list[str]:
    """Remove standalone links and link labels from project entries."""

    cleaned = []
    ignored_labels = {
        "github",
        "live demo",
        "demo",
        "source code",
    }

    for line in lines:
        line = _clean_line(line)

        # Remove URLs.
        line = re.sub(
            r"https?://\S+|www\.\S+",
            "",
            line,
            flags=re.IGNORECASE,
        )

        # Remove standalone link labels separated by pipes.
        parts = re.split(r"\s*\|\s*", line)

        meaningful_parts = [
            part.strip()
            for part in parts
            if part.strip().lower() not in ignored_labels
        ]

        line = " ".join(meaningful_parts)
        line = re.sub(r"\s+", " ", line).strip(" -|")

        if not line:
            continue

        if line.lower() in ignored_labels:
            continue

        cleaned.append(line)

    return list(dict.fromkeys(cleaned))[:30]

def _extract_projects(lines: list[str]) -> list[dict[str, Any]]:
    """Group project titles, technologies and descriptions."""

    projects = []
    current = None

    excluded = {
        "github", "live demo", "github | live demo",
        "demo", "source code", "technologies", "tools used"
    }

    tech_pattern = re.compile(
        r"^(python|java|javascript|typescript|react|fastapi|"
        r"tensorflow|pytorch|postgresql|docker|langchain|"
        r"scikit-learn|hugging face|streamlit)\b",
        re.I
    )

    def save_project():
        nonlocal current

        if current:
            current["description"] = " ".join(
                current["description"]
            ).strip()

            current["technologies"] = list(
                dict.fromkeys(current["technologies"])
            )

            projects.append(current)

        current = None

    for raw_line in lines:
        line = _clean_line(raw_line)

        if not line:
            continue

        # Remove repository/demo labels from project headings.
        line = re.sub(
            r"\s*\|\s*(github|live demo|demo|source code).*$",
            "",
            line,
            flags=re.I
        ).strip()

        lower = line.lower()

        if lower in excluded:
            continue

        if re.match(r"^(https?://|www\.)", line, re.I):
            continue

        # Identify short project-heading lines.
        is_title = (
            len(line) <= 100
            and not line.endswith((".", ",", ";", ":"))
            and not tech_pattern.match(line)
            and not line.lower().startswith((
                "built ", "developed ", "designed ",
                "implemented ", "engineered ",
                "evaluated ", "created "
            ))
        )

        if is_title:
            save_project()

            current = {
                "title": line,
                "technologies": [],
                "description": []
            }
            continue

        if current is None:
            continue

        if tech_pattern.match(line) and line.count(",") >= 2:
            current["technologies"].extend(
                item.strip()
                for item in line.split(",")
                if item.strip()
            )
        else:
            current["description"].append(line)

    save_project()

    return projects


def _extract_experience(
    sections: dict[str, list[str]],
    current_date: date,
) -> dict[str, Any]:

    professional_lines = sections.get("experience", [])
    internship_lines = sections.get("internships", [])
    project_lines = sections.get("projects", [])

    all_text = "\n".join(
        line
        for values in sections.values()
        for line in values
    )

    stated = [
        float(value)
        for value in re.findall(
            r"\b(\d+(?:\.\d+)?)\s*\+?\s*years?"
            r"\s+(?:of\s+)?(?:professional\s+)?experience\b",
            all_text,
            re.IGNORECASE,
        )
    ]

    (
        professional_intervals,
        classified_internship_intervals,
        professional_evidence,
        classified_internship_evidence,
        ambiguous_evidence,
    ) = _extract_employment_intervals(
        professional_lines,
        current_date,
    )

    (
        _,
        internship_section_intervals,
        _,
        internship_section_evidence,
        internship_ambiguous,
    ) = _extract_employment_intervals(
        internship_lines,
        current_date,
    )

    internship_intervals = (
        classified_internship_intervals
        + internship_section_intervals
    )

    # FIX: Initialize evidence before extending it.
    internship_evidence = list(
        classified_internship_evidence
    )

    internship_evidence.extend(
        internship_section_evidence
    )

    ambiguous_evidence.extend(
        internship_ambiguous
    )

    professional_years = _calculate_cumulative_experience(
        professional_intervals
    )

    internship_years = _calculate_cumulative_experience(
        internship_intervals
    )

    return {
        "professional_experience_years": professional_years,

        "internship_experience_years": internship_years,

        "stated_experience_years": max(
            stated,
            default=None,
        ),

        "experience_evidence": professional_evidence[:30],

        "internship_evidence": list(
            dict.fromkeys(internship_evidence)
        )[:30],

        "project_evidence": project_lines[:30],

        "ambiguous_date_evidence": list(
            dict.fromkeys(ambiguous_evidence)
        )[:30],

        "experience_calculation_note": (
            "Employment experience is calculated from recognizable "
            "date ranges associated with employment-related context. "
            "Overlapping periods are counted once within each category. "
            "Internships are reported separately. Ambiguous dates are "
            "retained for review rather than automatically counted."
        ),
    }


def _extract_education_details(lines: list[str]) -> list[dict[str, Any]]:
    results = []

    degree_pattern = re.compile(
        r"\b(B\.?Tech|B\.?E\.?|M\.?Tech|M\.?E\.?|"
        r"B\.?Sc|M\.?Sc|BCA|MCA|MBA|Ph\.?D|"
        r"Bachelor(?:'s)?|Master(?:'s)?)\b",
        re.IGNORECASE,
    )

    year_pattern = re.compile(r"\b(?:19|20)\d{2}\b")

    for line in lines:
        degree = degree_pattern.search(line)
        years = year_pattern.findall(line)

        if not degree:
            continue

        results.append({
            "degree": degree.group(0),
            "institution": line,
            "start_year": years[0] if len(years) >= 2 else None,
            "end_year": years[-1] if years else None,
            "evidence": line,
        })

    return results

def _parse_employment_date_range(line: str) -> tuple[str | None, str | None]:
    """
    Extract start and end dates from a resume line.
    Supports:
    Jan 2023 - Dec 2024
    01/2023 - 12/2024
    2022 - 2024
    Jan 2023 - Present
    """

    date_pattern = (
        r"(?:"
        r"[A-Za-z]{3,9}\.?\s+(?:19|20)\d{2}"
        r"|"
        r"(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}"
        r"|"
        r"(?:19|20)\d{2}"
        r"|"
        r"Present|Current|Now"
        r")"
    )

    match = re.search(
        rf"(?P<start>{date_pattern})\s*(?:-|–|—|to)\s*"
        rf"(?P<end>{date_pattern})",
        line,
        re.IGNORECASE,
    )

    if not match:
        return None, None

    return match.group("start").strip(), match.group("end").strip()


def _classify_employment_type(text: str) -> str:
    """Classify employment only when the resume provides evidence."""

    text = text.lower()

    if re.search(r"\b(intern|internship|student intern)\b", text):
        return "internship"

    if re.search(r"\b(full[- ]time|fulltime)\b", text):
        return "full_time"

    if re.search(r"\b(part[- ]time|parttime)\b", text):
        return "part_time"

    if re.search(r"\b(contract|contractual)\b", text):
        return "contract"

    if re.search(r"\b(freelance|freelancer)\b", text):
        return "freelance"

    return "unknown"


def _extract_job_title_and_company(lines: list[str]) -> tuple[str | None, str | None]:
    """
    Extract title and company from a header such as:
    Software Engineer | ABC Technologies
    Data Analyst at XYZ Ltd
    Machine Learning Intern — ABC
    """

    for line in lines:
        cleaned = _clean_line(line)

        if not cleaned:
            continue

        # Ignore bullet points and likely responsibility statements.
        if re.search(
            r"\b(developed|built|created|implemented|managed|"
            r"responsible for|worked on|designed|analyzed|analysed)\b",
            cleaned,
            re.IGNORECASE,
        ):
            continue

        parts = re.split(
            r"\s+\|\s+|\s+@\s+|\s+at\s+|\s+[—–]\s+",
            cleaned,
            maxsplit=1,
            flags=re.IGNORECASE,
        )

        if len(parts) == 2:
            title = _clean_line(parts[0])
            company = _clean_line(parts[1])

            return title or None, company or None

        # Preserve a possible title without inventing a company.
        if len(cleaned.split()) <= 8:
            return cleaned, None

    return None, None


def _extract_employment_entries(
    sections: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """
    Extract individual employment records from Experience and Internship
    sections. Responsibilities and technologies remain evidence-based.
    """

    entries = []

    section_names = ("experience", "internships")

    for section_name in section_names:
        lines = sections.get(section_name, [])

        if not lines:
            continue

        # Date lines act as anchors for individual employment records.
        date_indexes = [
            index
            for index, line in enumerate(lines)
            if _parse_employment_date_range(line) != (None, None)
        ]

        for position, date_index in enumerate(date_indexes):
            start_date, end_date = _parse_employment_date_range(
                lines[date_index]
            )

            previous_date_index = (
                date_indexes[position - 1]
                if position > 0
                else -1
            )

            next_date_index = (
                date_indexes[position + 1]
                if position + 1 < len(date_indexes)
                else len(lines)
            )

            # Lines between the previous date and current date usually
            # contain the role title and company.
            header_lines = lines[
                previous_date_index + 1:date_index
            ]

            # Lines after the date usually contain responsibilities.
            following_lines = lines[
                date_index + 1:next_date_index
            ]

            # Limit the evidence window to avoid absorbing another role.
            header_lines = header_lines[-3:]
            following_lines = following_lines[:12]

            job_title, company = _extract_job_title_and_company(
                header_lines
            )

            evidence = list(dict.fromkeys(
                header_lines
                + [lines[date_index]]
                + following_lines
            ))

            responsibilities = [
                line for line in following_lines
                if len(line.split()) >= 4
                and not _parse_employment_date_range(line) != (None, None)
            ]

            employment_context = " ".join(evidence)
            
            employment_type = _classify_employment_type(
                employment_context
            )

            if section_name == "internships":
                employment_type = "internship"

            # Extract technologies directly from employment evidence.
            # This avoids relying on section-based skill extraction.
            technologies = []
            for canonical, aliases in SKILL_ALIASES.items():
                for alias in aliases:
                    pattern = (
                        r"(?<![a-zA-Z0-9_])"
                        + re.escape(alias)
                        + r"(?![a-zA-Z0-9_])"
                        )
                    if re.search(pattern, employment_context, re.IGNORECASE):
                        technologies.append(canonical)
                        break
            technologies = sorted(set(technologies))

            entries.append({
                "job_title": job_title,
                "company": company,
                "start_date": start_date,
                "end_date": end_date,
                "employment_type": employment_type,
                "responsibilities": responsibilities,
                "technologies": technologies,
                "evidence": evidence,
            })

    return entries


def extract_resume_intelligence(text: str, current_date: date | None = None) -> dict[str, Any]:
    """Return structured, evidence-backed candidate data from extracted resume text."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Resume text is empty. No candidate information can be extracted.")

    current_date = current_date or date.today()
    sections = split_sections(text)
    lines = [line for line in text.splitlines() if _clean_line(line)]

    email_match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I)
    phone_match = re.search(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", text)

    linkedin_match = re.search(
        r"(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+",
        text,
        re.IGNORECASE,
    )

    github_match = re.search(
        r"(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9_-]+",
        text,
        re.IGNORECASE,
    )

    name = None
    for line in lines[:6]:
        candidate = _clean_line(line)
        if (
            1 <= len(candidate.split()) <= 4
            and not re.search(r"@|resume|curriculum|phone|email|linkedin|http|\d", candidate, re.I)
            and not _section_key(candidate.rstrip(":"))
        ):
            name = candidate
            break

    skills = _find_skill_mentions(text, sections)
    experience = _extract_experience(sections, current_date)
    experience["employment_entries"] = _extract_employment_entries(sections)
    education_lines = sections.get("education", [])
    certification_lines = sections.get("certifications", [])
    project_lines = sections.get("projects", [])

    education_details = _extract_education_details(education_lines)

    return {
        "candidate": {
            "name": name,
            "email": email_match.group(0) if email_match else None,
            "phone": phone_match.group(0).strip() if phone_match else None,
            "linkedin": linkedin_match.group(0) if linkedin_match else None,
            "github": github_match.group(0) if github_match else None,
        },
        "skills": skills,
        "experience": experience,
        "education": education_lines[:30],
        "education_details": education_details,
        "certifications": certification_lines[:30],
        "projects": _extract_projects(project_lines),
        "sections": sections,
        "extraction_metadata": {
            "has_name": name is not None,
            "has_email": email_match is not None,
            "has_phone": phone_match is not None,
            "skill_count": len(skills),
            "sections_found": sorted(sections.keys()),
            "warnings": [],
        },
    }