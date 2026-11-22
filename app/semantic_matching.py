"""
TalentIQ - Hybrid Semantic Matching Engine

Features:
1. Exact skill matching.
2. Related skill identification.
3. Semantic similarity using Sentence Transformers.
4. Evidence-based requirement matching.
5. Missing and unverified skill identification.
6. Requirement-level matching reports.

Semantic similarity alone never establishes that a candidate
possesses a mandatory technical skill.
"""

from functools import lru_cache
from typing import Any

import numpy as np

import numpy as np

from app.resume_intelligence import SKILL_ALIASES


# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

RELATED_SKILLS = {

    # ==========================================
    # TECHNOLOGY
    # ==========================================

    "natural language processing": {
        "bert", "transformers", "hugging face",
        "text classification"
    },

    "machine learning": {
        "deep learning", "scikit-learn",
        "tensorflow", "pytorch"
    },

    "deep learning": {
        "pytorch", "tensorflow", "keras",
        "transformers"
    },

    "generative ai": {
        "large language models",
        "retrieval augmented generation",
        "langchain"
    },

    "large language models": {
        "generative ai",
        "retrieval augmented generation",
        "transformers"
    },

    "backend development": {
        "fastapi", "flask", "django", "rest api"
    },

    # ==========================================
    # HUMAN RESOURCES & RECRUITMENT
    # ==========================================

    "talent acquisition": {
        "recruitment coordination",
        "candidate sourcing",
        "recruitment"
    },

    "recruitment coordination": {
        "interview scheduling",
        "candidate communication",
        "candidate follow-ups"
    },

    "resume screening": {
        "candidate evaluation",
        "cv screening",
        "applicant screening"
    },

    "candidate sourcing": {
        "talent sourcing",
        "profile sourcing",
        "job portal sourcing"
    },

    "applicant tracking system": {
        "ats",
        "zoho recruit",
        "applicant tracking"
    },

    "interview scheduling": {
        "interview coordination",
        "calendar management"
    },

    "candidate relationship management": {
        "candidate engagement",
        "candidate communication",
        "candidate follow-ups"
    },

    "hr operations": {
        "onboarding",
        "employee documentation",
        "hr documentation"
    },

    "recruitment reporting": {
        "recruitment metrics",
        "hiring reports",
        "recruitment mis"
    },

    # ==========================================
    # BUSINESS & OPERATIONS
    # ==========================================

    "business analysis": {
        "requirements gathering",
        "process analysis",
        "stakeholder communication"
    },

    "project management": {
        "project coordination",
        "task management",
        "milestone tracking"
    },

    "operations management": {
        "process coordination",
        "workflow management",
        "operations coordination"
    },

    "data analysis": {
        "data interpretation",
        "data visualization",
        "reporting"
    },

    # ==========================================
    # FINANCE & ACCOUNTING
    # ==========================================

    "financial analysis": {
        "financial reporting",
        "budget analysis",
        "variance analysis"
    },

    "accounting": {
        "bookkeeping",
        "accounts reconciliation",
        "financial statements"
    },

    # ==========================================
    # PROFESSIONAL COMPETENCIES
    # ==========================================

    "communication skills": {
        "verbal communication",
        "written communication",
        "stakeholder communication"
    },

    "teamwork": {
        "team collaboration",
        "interpersonal skills",
        "cross-functional collaboration"
    },

    "time management": {
        "organizational skills",
        "task prioritization",
        "multitasking"
    },

    "problem solving": {
        "analytical thinking",
        "critical thinking",
        "troubleshooting"
    }
}

DEFAULT_SIMILARITY_THRESHOLD = 0.55


# --------------------------------------------------
# 2. MODEL LOADING
# --------------------------------------------------

@lru_cache(maxsize=1)
def load_embedding_model():
    """
    Load Sentence Transformer only when semantic matching
    actually requires it.

    Cache the model so it is loaded only once.
    """

    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            MODEL_NAME,
            device="cpu"
        )

    except Exception as exc:
        raise RuntimeError(
            f"Unable to load semantic model: {MODEL_NAME}"
        ) from exc


# --------------------------------------------------
# 3. NORMALIZATION
# --------------------------------------------------

def normalize_skill(skill: str) -> str:

    skill = str(skill).strip().lower()

    skill = " ".join(skill.split())

    for canonical, aliases in SKILL_ALIASES.items():

        if skill == canonical.lower():

            return canonical

        if skill in {
            alias.lower()
            for alias in aliases
        }:

            return canonical

    return skill


# --------------------------------------------------
# 4. EXTRACT CANDIDATE SKILLS
# --------------------------------------------------

def get_candidate_skills(profile: dict) -> list[str]:

    raw_skills = profile.get("skills", [])

    normalized = set()

    for item in raw_skills:

        if isinstance(item, dict):

            skill = item.get("name")

        else:

            skill = item

        if skill:

            normalized.add(
                normalize_skill(skill)
            )

    return sorted(normalized)


# --------------------------------------------------
# 5. EXTRACT CANDIDATE EVIDENCE
# --------------------------------------------------

def get_candidate_evidence(profile: dict) -> list[str]:
    evidence = []

    def collect(items):
        if isinstance(items, str):
            value = items.strip()
            if value:
                evidence.append(value)

        elif isinstance(items, (list, tuple)):
            for item in items:
                collect(item)

    # Skill-level evidence
    for skill in profile.get("skills", []) or []:
        if isinstance(skill, dict):
            collect(skill.get("evidence", []))
            collect(skill.get("evidence_sentences", []))

    # Experience-level evidence
    experience = profile.get("experience", {}) or {}

    if isinstance(experience, dict):
        collect(experience.get("experience_evidence", []))
        collect(experience.get("internship_evidence", []))
        collect(experience.get("project_evidence", []))

        # Include responsibilities from structured employment entries
        for entry in experience.get("employment_entries", []) or []:
            if isinstance(entry, dict):
                collect(entry.get("responsibilities", []))
                collect(entry.get("evidence", []))

    # Legacy profile compatibility
    collect(profile.get("experience_evidence", []))
    collect(profile.get("project_evidence", []))
    collect(profile.get("projects", []))

    return list(dict.fromkeys(evidence))


# --------------------------------------------------
# 6. COSINE SIMILARITY
# --------------------------------------------------

def cosine_similarity(
    vector_a: np.ndarray,
    vector_b: np.ndarray
) -> float:

    vector_a = np.asarray(vector_a, dtype=float)

    vector_b = np.asarray(vector_b, dtype=float)

    denominator = (
        np.linalg.norm(vector_a)
        * np.linalg.norm(vector_b)
    )

    if denominator == 0:

        return 0.0

    similarity = np.dot(
        vector_a,
        vector_b
    ) / denominator

    return float(
        np.clip(similarity, -1.0, 1.0)
    )


# --------------------------------------------------
# 7. SEMANTIC SIMILARITY ENGINE
# --------------------------------------------------

def calculate_semantic_similarity(
    requirement: str,
    evidence: str,
    model=None
) -> float:

    if not requirement.strip() or not evidence.strip():

        return 0.0

    if model is None:

        model = load_embedding_model()

    embeddings = model.encode(
        [requirement, evidence],
        convert_to_numpy=True,
        normalize_embeddings=False
    )

    similarity = cosine_similarity(
        embeddings[0],
        embeddings[1]
    )

    return round(
        max(0.0, similarity),
        4
    )


# --------------------------------------------------
# 8. RELATED SKILL DETECTION
# --------------------------------------------------

def find_related_skills(
    required_skill: str,
    candidate_skills: list[str]
) -> list[str]:

    required_skill = normalize_skill(
        required_skill
    )

    related = RELATED_SKILLS.get(
        required_skill,
        set()
    )

    matched = []

    for candidate_skill in candidate_skills:

        normalized = normalize_skill(
            candidate_skill
        )

        if normalized in related:

            matched.append(normalized)

    return sorted(set(matched))


# --------------------------------------------------
# 9. MATCH ONE REQUIREMENT
# --------------------------------------------------

def match_requirement(
    requirement: str,
    candidate_skills: list[str],
    evidence: list[str],
    model=None,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> dict[str, Any]:

    candidate_skills = candidate_skills or []
    evidence = evidence or []

    required = normalize_skill(requirement)

    normalized_skills = {
        normalize_skill(skill)
        for skill in candidate_skills
        if skill
    }

    # ----------------------------------------------
    # Exact skill match
    # ----------------------------------------------

    if required in normalized_skills:
        return {
            "requirement": required,
            "status": "exact_match",
            "match_type": "exact",
            "similarity": 1.0,
            "matched_skill": required,
            "related_skills": [],
            "supporting_evidence": [],
            "explanation": (
                f"Candidate explicitly lists {required}."
            )
        }

    # ----------------------------------------------
    # Related skill identification
    # ----------------------------------------------

    related = find_related_skills(
        required,
        candidate_skills
    )

    # ----------------------------------------------
    # Semantic evidence comparison
    # ----------------------------------------------

    best_similarity = 0.0
    best_evidence = None

    for item in evidence:

        if not isinstance(item, str) or not item.strip():
            continue

        similarity = calculate_semantic_similarity(
            required,
            item,
            model=model
        )

        if similarity > best_similarity:
            best_similarity = similarity
            best_evidence = item

    # ----------------------------------------------
    # Related skill with evidence
    # ----------------------------------------------

    if related:

        supporting_evidence = []

        for item in evidence:

            if not isinstance(item, str):
                continue

            similarity = calculate_semantic_similarity(
                required,
                item,
                model=model
            )

            if similarity >= threshold:
                supporting_evidence.append(item)

        return {
            "requirement": required,
            "status": "related_match",
            "match_type": "related",
            "similarity": best_similarity,
            "matched_skill": None,
            "related_skills": related,
            "supporting_evidence": supporting_evidence,
            "explanation": (
                f"Candidate lists related capabilities: "
                f"{', '.join(related)}. "
                "Direct proficiency in the required skill "
                "has not been established."
            )
        }

    # ----------------------------------------------
    # Demonstrated competency through experience
    # ----------------------------------------------

    if best_similarity >= threshold:

        return {
            "requirement": required,
            "status": "needs_verification",
            "match_type": "demonstrated_evidence",
            "similarity": best_similarity,
            "matched_skill": None,
            "related_skills": [],
            "supporting_evidence": [
                best_evidence
            ] if best_evidence else [],
            "explanation": (
                "Relevant evidence was identified in the "
                "candidate's resume. This may demonstrate "
                "the required competency, but manual "
                "verification is recommended."
            )
        }

    # ----------------------------------------------
    # No supporting evidence
    # ----------------------------------------------

    return {
        "requirement": required,
        "status": "unverified",
        "match_type": "none",
        "similarity": best_similarity,
        "matched_skill": None,
        "related_skills": [],
        "supporting_evidence": [],
        "explanation": (
            f"No sufficient evidence found for {required}."
        )
    }


def deduplicate_requirements(
    required_skills: list[str],
    preferred_skills: list[str]
) -> tuple[list[str], list[str]]:

    required = []
    preferred = []

    required_seen = set()

    for skill in required_skills:
        normalized = normalize_skill(skill)

        if normalized not in required_seen:
            required.append(normalized)
            required_seen.add(normalized)

    preferred_seen = set()

    for skill in preferred_skills:
        normalized = normalize_skill(skill)

        # Required skills take priority.
        if normalized in required_seen:
            continue

        if normalized not in preferred_seen:
            preferred.append(normalized)
            preferred_seen.add(normalized)

    return required, preferred


# --------------------------------------------------
# 10. HYBRID MATCHING ENGINE
# --------------------------------------------------

def match_candidate(
    jd: dict,
    profile: dict,
    model=None,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD
) -> dict[str, Any]:

    candidate_skills = get_candidate_skills(
        profile
    )

    evidence = get_candidate_evidence(
        profile
    )

    required_skills = jd.get(
        "required_skills",
        []
    )

    preferred_skills = jd.get(
        "preferred_skills",
        []
    )

    required_skills, preferred_skills = deduplicate_requirements(
    required_skills,
    preferred_skills
)

    # ----------------------------------------------
    # Match mandatory requirements
    # ----------------------------------------------

    required_results = []

    for skill in required_skills:

        result = match_requirement(
            skill,
            candidate_skills,
            evidence,
            model,
            threshold
        )

        result["importance"] = "mandatory"

        required_results.append(result)

    # ----------------------------------------------
    # Match preferred requirements
    # ----------------------------------------------

    preferred_results = []

    for skill in preferred_skills:

        result = match_requirement(
            skill,
            candidate_skills,
            evidence,
            model,
            threshold
        )

        result["importance"] = "preferred"

        preferred_results.append(result)

    # ----------------------------------------------
    # Calculate matching statistics
    # ----------------------------------------------

    all_results = (
        required_results
        + preferred_results
    )

    exact_count = sum(
        item["status"] == "exact_match"
        for item in all_results
    )

    related_count = sum(
        item["status"] == "related_match"
        for item in all_results
    )

    verification_count = sum(
        item["status"] == "needs_verification"
        for item in all_results
    )

    unverified_count = sum(
        item["status"] == "unverified"
        for item in all_results
    )

    return {

        "required_skill_analysis": required_results,

        "preferred_skill_analysis": preferred_results,

        "statistics": {

            "total_requirements": len(all_results),

            "exact_matches": exact_count,

            "related_matches": related_count,

            "needs_verification": verification_count,

            "unverified": unverified_count,

        },

        "candidate_skills": candidate_skills,

        "evidence_count": len(evidence),

        "matching_method": "hybrid_semantic_and_skill_matching"

    }