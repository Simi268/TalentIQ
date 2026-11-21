"""
TalentIQ - Job Description Intelligence Engine

Responsibilities:
1. Extract job title.
2. Identify mandatory and preferred skills.
3. Extract experience requirements.
4. Extract educational qualifications.
5. Identify job responsibilities.
6. Extract certifications.
7. Preserve evidence for every extracted requirement.

This module uses rule-based NLP and a normalized skill taxonomy.
It does not fabricate missing information.
"""

import re
from typing import Optional

from app.resume_intelligence import SKILL_ALIASES


# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

MANDATORY_KEYWORDS = [
    "must have",
    "must possess",
    "required",
    "mandatory",
    "essential",
    "minimum requirement",
    "minimum qualification",
    "you must",
    "strong proficiency in",
    "proficiency in",
    "expertise in",
]

PREFERRED_KEYWORDS = [
    "preferred",
    "preferably",
    "nice to have",
    "good to have",
    "bonus",
    "desirable",
    "an advantage",
    "would be beneficial",
    "plus",
]

RESPONSIBILITY_KEYWORDS = [
    "responsible for",
    "responsibilities",
    "you will",
    "develop",
    "design",
    "implement",
    "maintain",
    "build",
    "manage",
    "collaborate",
    "analyze",
    "deploy",
    "optimize",
    "create",
]

EDUCATION_KEYWORDS = [
    "bachelor",
    "master",
    "b.tech",
    "m.tech",
    "b.e.",
    "b.sc",
    "m.sc",
    "phd",
    "degree",
    "graduate",
    "computer science",
    "engineering",
]

CERTIFICATION_KEYWORDS = [
    "certification",
    "certified",
    "certificate",
    "aws certified",
    "azure certified",
    "google cloud certified",
]


# --------------------------------------------------
# 2. TEXT PREPROCESSING
# --------------------------------------------------

def clean_text(text: str) -> str:

    if not isinstance(text, str):
        raise TypeError("Job description must be a string.")

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_sentences(text: str) -> list[str]:

    sentences = re.split(
        r"(?<=[.!?])\s+|\n+",
        text
    )

    return [
        sentence.strip(" •-\t")
        for sentence in sentences
        if sentence.strip(" •-\t")
    ]


# --------------------------------------------------
# 3. JOB TITLE EXTRACTION
# --------------------------------------------------

def extract_job_title(text: str) -> Optional[str]:

    lines = [
        line.strip(" :-•\t")
        for line in text.splitlines()
        if line.strip()
    ]

    title_patterns = [
        r"(?:job title|position|role)\s*:\s*(.+)",
        r"(?:we are hiring|hiring for)\s+(?:an?\s+)?(.+)",
        r"(?:opening for)\s+(?:an?\s+)?(.+)",
    ]

    for line in lines[:15]:

        for pattern in title_patterns:

            match = re.search(
                pattern,
                line,
                re.IGNORECASE
            )

            if match:
                return match.group(1).strip()

    # Fallback: first short heading-like line.
    for line in lines[:5]:

        if (
            len(line.split()) <= 8
            and len(line) <= 90
            and not re.search(
                r"responsibilities|qualifications|requirements|about us",
                line,
                re.IGNORECASE
            )
        ):
            return line

    return None


# --------------------------------------------------
# 4. REQUIREMENT CLASSIFICATION
# --------------------------------------------------

def classify_requirement(sentence: str) -> str:

    normalized = sentence.lower()

    mandatory = any(
        keyword in normalized
        for keyword in MANDATORY_KEYWORDS
    )

    preferred = any(
        keyword in normalized
        for keyword in PREFERRED_KEYWORDS
    )

    if mandatory and not preferred:
        return "mandatory"

    if preferred and not mandatory:
        return "preferred"

    return "unspecified"


# --------------------------------------------------
# 5. SKILL EXTRACTION
# --------------------------------------------------
SECTION_TYPES = {
    "mandatory": {
        "required skills",
        "mandatory skills",
        "must have",
        "required qualifications",
        "requirements",
    },
    "preferred": {
        "preferred skills",
        "nice to have",
        "good to have",
        "bonus skills",
    },
    "responsibilities": {
        "responsibilities",
        "key responsibilities",
        "what you will do",
        "what you'll do",
        "your responsibilities",
    },
    "education": {
        "education",
        "educational qualifications",
        "academic qualifications",
    },
    "experience": {
        "experience",
        "experience requirements",
        "work experience",
    },
    "certifications": {
        "certifications",
        "certificates",
    },
}


def get_section_type(line):
    heading = line.strip().lower()
    heading = heading.lstrip("#").strip()
    heading = heading.rstrip(":").strip()

    for section, headings in SECTION_TYPES.items():
        if heading in headings:
            return section

    return None


def extract_skills(text: str) -> dict:

    extracted = {}
    current_section = None

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        detected_section = get_section_type(line)

        if detected_section:
            current_section = detected_section
            continue

        # Process individual sentences, not entire lines.
        sentences = split_sentences(line)

        for sentence in sentences:

            explicit_classification = classify_requirement(sentence)

            # Explicit sentence-level classification takes priority.
            if explicit_classification != "unspecified":
                classification = explicit_classification

            elif current_section == "mandatory":
                classification = "mandatory"

            elif current_section == "preferred":
                classification = "preferred"

            else:
                classification = "unspecified"

            for canonical, aliases in SKILL_ALIASES.items():

                for alias in aliases:

                    pattern = (
                        r"(?<![a-z0-9+#])"
                        + re.escape(alias.lower())
                        + r"(?![a-z0-9+#])"
                    )

                    if not re.search(pattern, sentence.lower()):
                        continue

                    if canonical not in extracted:
                        extracted[canonical] = {
                            "name": canonical,
                            "classification": classification,
                            "evidence": [],
                            "evidence_sentences": [],
                        }

                    item = extracted[canonical]

                    if sentence not in item["evidence_sentences"]:
                        item["evidence_sentences"].append(sentence)

                    if classification not in item["evidence"]:
                        item["evidence"].append(classification)

                    if classification == "mandatory":
                        item["classification"] = "mandatory"

                    elif (
                        classification == "preferred"
                        and item["classification"] == "unspecified"
                    ):
                        item["classification"] = "preferred"

                    break

    mandatory = []
    preferred = []
    unspecified = []

    for skill, data in extracted.items():

        classification = data["classification"]

        if classification == "mandatory":
            mandatory.append(skill)

        elif classification == "preferred":
            preferred.append(skill)

        else:
            unspecified.append(skill)

    return {
        "all_skills": list(extracted.keys()),
        "required_skills": mandatory,
        "preferred_skills": preferred,
        "unclassified_skills": unspecified,
        "skill_evidence": extracted,
    }


# --------------------------------------------------
# 6. EXPERIENCE EXTRACTION
# --------------------------------------------------

def extract_experience(text: str) -> dict:
    """Extract minimum and maximum years of experience with evidence."""

    if not isinstance(text, str) or not text.strip():
        return {
            "minimum_experience": None,
            "maximum_experience": None,
            "experience_evidence": None,
        }

    patterns = [
        # 0-1 years, 1–3 years, 2 to 5 years
        (
            r"\b(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*"
            r"(\d+(?:\.\d+)?)\s*\+?\s*years?\b",
            True,
        ),
        # 3+ years, 3 years+
        (
            r"\b(\d+(?:\.\d+)?)\s*\+?\s*years?\s*\+?\b",
            False,
        ),
        # Minimum of 2 years, at least 2 years
        (
            r"\b(?:minimum(?:\s+of)?|at\s+least)\s+"
            r"(\d+(?:\.\d+)?)\s+years?\b",
            False,
        ),
        # 2 years of experience, 2 years experience
        (
            r"\b(\d+(?:\.\d+)?)\s+years?\s+"
            r"(?:of\s+)?experience\b",
            False,
        ),
        # Experience of 2 years
        (
            r"\bexperience\s+of\s+"
            r"(\d+(?:\.\d+)?)\s+years?\b",
            False,
        ),
    ]

    for pattern, is_range in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            continue

        minimum = float(match.group(1))
        maximum = float(match.group(2)) if is_range else None

        if maximum is not None and maximum < minimum:
            continue

        return {
            "minimum_experience": minimum,
            "maximum_experience": maximum,
            "experience_evidence": match.group(0),
        }

    return {
        "minimum_experience": None,
        "maximum_experience": None,
        "experience_evidence": None,
    }


def extract_education(text: str) -> list:

    education = []

    for sentence in split_sentences(text):

        lower = sentence.lower()

        if any(
            keyword in lower
            for keyword in EDUCATION_KEYWORDS
        ):
            education.append(sentence.strip(" •-*"))

    return list(dict.fromkeys(education))


# --------------------------------------------------
# 8. CERTIFICATION EXTRACTION
# --------------------------------------------------

def extract_certifications(text: str) -> list:

    certifications = []

    for sentence in split_sentences(text):

        lower = sentence.lower()

        if any(
            keyword in lower
            for keyword in CERTIFICATION_KEYWORDS
        ):
            certifications.append(sentence.strip(" •-*"))

    return list(dict.fromkeys(certifications))


# --------------------------------------------------
# 9. RESPONSIBILITY EXTRACTION
# --------------------------------------------------

def extract_responsibilities(text: str) -> list:

    lines = text.splitlines()

    responsibilities = []
    inside_responsibilities = False

    for line in lines:

        line = line.strip()

        if not line:
            continue

        section = get_section_type(line)

        if section:
            inside_responsibilities = (
                section == "responsibilities"
            )
            continue

        if inside_responsibilities:
            responsibilities.append(line)

    return list(dict.fromkeys(responsibilities))


# --------------------------------------------------
# 10. MAIN JD INTELLIGENCE PIPELINE
# --------------------------------------------------

def analyze_jd(text: str) -> dict:

    if not isinstance(text, str) or not text.strip():

        raise ValueError(
            "Job description cannot be empty."
        )

    cleaned = clean_text(text)

    skills = extract_skills(cleaned)

    experience = extract_experience(cleaned)

    education = extract_education(cleaned)

    certifications = extract_certifications(cleaned)

    responsibilities = extract_responsibilities(cleaned)

    job_title = extract_job_title(cleaned)

    return {

        "job_title": job_title,

        "required_skills": skills["required_skills"],

        "preferred_skills": skills["preferred_skills"],

        "unclassified_skills": skills["unclassified_skills"],

        "all_skills": skills["all_skills"],

        "skill_evidence": skills["skill_evidence"],

        "minimum_experience": experience["minimum_experience"],

        "maximum_experience": experience["maximum_experience"],
 
        "experience_evidence": experience["experience_evidence"], 

        "education": education,

        "certifications": certifications,

        "responsibilities": responsibilities,

        "metadata": {

            "total_skills": len(skills["all_skills"]),

            "mandatory_skill_count": len(
                skills["required_skills"]
            ),

            "preferred_skill_count": len(
                skills["preferred_skills"]
            ),

            "unclassified_skill_count": len(
                skills["unclassified_skills"]
            ),

            "has_experience_requirement": (
                experience["minimum_experience"] is not None
            ),

            "has_education_requirement": bool(education),

            "has_responsibilities": bool(responsibilities),
            "maximum_experience": experience["maximum_experience"],

        }

    }