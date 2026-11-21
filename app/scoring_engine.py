"""
TalentIQ - Explainable Candidate Scoring Engine

Evidence-based scoring with explicit evaluation coverage.
A provisional score is never presented as a fully evaluated score.
"""

from typing import Any
import math


# --------------------------------------------------
# 1. SCORING CONFIGURATION
# --------------------------------------------------

SCORING_WEIGHTS = {
    "required_skills": 35.0,
    "semantic_relevance": 25.0,
    "experience": 20.0,
    "education": 10.0,
    "preferred_skills": 10.0,
}

SKILL_STATUS_VALUES = {
    "exact_match": 1.0,
    "related_match": 0.50,
    "needs_verification": 0.25,
}

VALID_SKILL_STATUSES = {
    "exact_match",
    "related_match",
    "needs_verification",
    "unverified",
    "missing",
}


# --------------------------------------------------
# 2. VALIDATION AND UTILITIES
# --------------------------------------------------

def validate_weights(weights: dict[str, float] | None = None) -> None:
    weights = SCORING_WEIGHTS if weights is None else weights

    if not isinstance(weights, dict) or not weights:
        raise ValueError("Scoring weights must be a non-empty dictionary.")

    if any(
        not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0
        for value in weights.values()
    ):
        raise ValueError(
            "Scoring weights must be finite, non-negative numbers."
        )

    if abs(sum(float(v) for v in weights.values()) - 100.0) > 0.0001:
        raise ValueError("Scoring weights must sum to 100.")


def clamp_score(value: float) -> float:
    value = float(value)

    if not math.isfinite(value):
        raise ValueError("Score must be a finite number.")

    return round(max(0.0, min(100.0, value)), 2)


def _as_list(value: Any) -> list:
    if value is None:
        return []

    return value if isinstance(value, list) else [value]


def _normalise_text(value: Any) -> str:
    """Flatten common education/profile values into searchable text."""

    if value is None:
        return ""

    if isinstance(value, dict):
        return " ".join(
            _normalise_text(v) for v in value.values()
        )

    if isinstance(value, (list, tuple, set)):
        return " ".join(
            _normalise_text(v) for v in value
        )

    return str(value).strip().lower()


# --------------------------------------------------
# 3. SKILL SCORING
# --------------------------------------------------

def calculate_skill_score(
    results: list[dict[str, Any]]
) -> dict[str, Any]:

    results = results or []

    if not results:
        return {
            "score": None,
            "coverage_score": None,
            "aggregation_score": None,
            "evaluated": 0,
            "total": 0,
            "coverage": 0.0,
            "details": [],
            "status": "not_evaluated",
        }

    total = len(results)
    earned = 0.0
    evaluated = 0
    details = []

    for result in results:

        status = result.get("status", "unverified")
        value = SKILL_STATUS_VALUES.get(status)

        if value is None:

            explanation = result.get("explanation") or (
                "The resume does not provide enough evidence to assess "
                "this requirement. Absence of evidence is not proof "
                "that the candidate lacks the skill."
            )

            details.append({
                "requirement": result.get("requirement"),
                "status": status,
                "score": None,
                "explanation": explanation,
            })

            continue

        earned += value
        evaluated += 1

        details.append({
            "requirement": result.get("requirement"),
            "status": status,
            "score": round(value * 100, 2),
            "explanation": result.get("explanation", ""),
        })

    verified_score = (
        clamp_score((earned / evaluated) * 100)
        if evaluated else None
    )

    coverage_score = clamp_score(
        (earned / total) * 100
    )

    coverage = round(
        (evaluated / total) * 100,
        2
    )

    return {
        "score": verified_score,
        "coverage_score": coverage_score,
        "aggregation_score": coverage_score,
        "evaluated": evaluated,
        "total": total,
        "coverage": coverage,
        "details": details,
        "status": "evaluated" if evaluated else "unverified",
    }


# --------------------------------------------------
# 4. SEMANTIC RELEVANCE SCORING
# --------------------------------------------------

def calculate_semantic_score(
    required_results: list[dict[str, Any]],
    preferred_results: list[dict[str, Any]],
) -> dict[str, Any]:

    results = (
        (required_results or [])
        + (preferred_results or [])
    )

    similarities = []

    for result in results:

        similarity = result.get("similarity")

        if similarity is None:
            continue

        try:
            similarity = float(similarity)

        except (TypeError, ValueError):
            continue

        if not math.isfinite(similarity):
            continue

        # The semantic matching module already clamps cosine
        # similarity to the range 0–1.
        similarities.append(
            max(0.0, min(1.0, similarity)) * 100
        )

    if not similarities:

        return {
            "score": None,
            "evaluated": 0,
            "status": "not_evaluated",
            "explanation": (
                "No usable semantic similarity values were produced."
            ),
        }

    return {
        "score": clamp_score(
            sum(similarities) / len(similarities)
        ),
        "evaluated": len(similarities),
        "status": "evaluated",
        "explanation": (
            f"Semantic similarity was evaluated for "
            f"{len(similarities)} requirement/evidence comparisons."
        ),
    }


# --------------------------------------------------
# 5. EXPERIENCE SCORING
# --------------------------------------------------

def calculate_experience_score(
    jd: dict,
    profile: dict
) -> dict[str, Any]:

    required = jd.get("minimum_experience")

    experience = profile.get("experience", {})

    if not isinstance(experience, dict):
        experience = {}

    actual = profile.get("relevant_experience_years")

    if actual is None:
        actual = experience.get(
            "relevant_experience_years"
        )

    if actual is None:
        actual = experience.get(
            "professional_experience_years"
        )

    if actual is None:
        actual = profile.get(
            "total_experience_years"
        )

    if required is None:
        return {
            "score": None,
            "required_years": None,
            "actual_years": actual,
            "status": "not_required",
            "explanation": (
                "The job description does not specify "
                "a minimum experience requirement."
            ),
        }

    try:
        required = float(required)

        if not math.isfinite(required) or required < 0:
            raise ValueError

    except (TypeError, ValueError):
        return {
            "score": None,
            "required_years": required,
            "actual_years": actual,
            "status": "needs_review",
            "explanation": (
                "The experience requirement could not "
                "be interpreted reliably."
            ),
        }

    # Zero years is not a differentiating requirement.
    if required == 0:
        return {
            "score": None,
            "required_years": 0.0,
            "actual_years": actual,
            "status": "not_required",
            "explanation": (
                "The role accepts candidates with zero years "
                "of experience; experience is therefore not "
                "scored as a differentiator."
            ),
        }

    if actual is None:
        return {
            "score": None,
            "required_years": required,
            "actual_years": None,
            "status": "unverified",
            "explanation": (
                "Relevant experience could not be established "
                "from the resume."
            ),
        }

    try:
        actual = float(actual)

        if not math.isfinite(actual) or actual < 0:
            raise ValueError

    except (TypeError, ValueError):
        return {
            "score": None,
            "required_years": required,
            "actual_years": actual,
            "status": "needs_review",
            "explanation": (
                "Extracted experience duration requires verification."
            ),
        }

    score = clamp_score(
        min(actual / required, 1.0) * 100
    )

    status = (
        "met"
        if actual >= required
        else "below_requirement"
    )

    return {
        "score": score,
        "required_years": required,
        "actual_years": actual,
        "status": status,
        "explanation": (
            f"Required experience: {required:g} years. "
            f"Resume-supported experience: {actual:g} years."
        ),
    }


# --------------------------------------------------
# 6. EDUCATION SCORING
# --------------------------------------------------

_DEGREE_GROUPS = {
    "doctorate": (
        "phd", "ph.d", "doctorate", "doctoral"
    ),

    "master": (
        "master", "m.tech", "mtech",
        "m.e", "m.e.", "m.sc", "msc", "mba"
    ),

    "bachelor": (
        "bachelor", "b.tech", "btech",
        "b.e", "b.e.", "b.sc", "bsc",
        "bca", "bba"
    ),

    "diploma": (
        "diploma", "polytechnic"
    ),
}

_FIELD_ALIASES = {
    "computer science": (
        "computer science",
        "cse",
        "computer science and engineering"
    ),

    "information technology": (
        "information technology",
        " it ",
        " it)",
        "(it"
    ),

    "electronics": (
        "electronics",
        "ece",
        "electrical and electronics"
    ),

    "data science": (
        "data science",
        "data analytics"
    ),

    "artificial intelligence": (
        "artificial intelligence",
        " ai ",
        "machine learning"
    ),
}


def _degree_level(text: str) -> str | None:

    padded = f" {text.lower()} "

    for level, aliases in _DEGREE_GROUPS.items():

        if any(alias in padded for alias in aliases):
            return level

    return None


def _field_match(
    required_text: str,
    candidate_text: str
) -> bool | None:

    required_fields = [
        canonical
        for canonical, aliases in _FIELD_ALIASES.items()
        if any(
            alias in f" {required_text} "
            for alias in aliases
        )
    ]

    if not required_fields:
        return None

    candidate_fields = [
        canonical
        for canonical, aliases in _FIELD_ALIASES.items()
        if any(
            alias in f" {candidate_text} "
            for alias in aliases
        )
    ]

    if not candidate_fields:
        return None

    return bool(
        set(required_fields) & set(candidate_fields)
    )


def calculate_education_score(
    jd: dict,
    profile: dict
) -> dict[str, Any]:

    requirements = jd.get("education")
    candidate_education = profile.get("education")

    if not requirements:
        return {
            "score": None,
            "status": "not_required",
            "explanation": (
                "No specific education requirement was "
                "identified in the job description."
            ),
        }

    if not candidate_education:
        return {
            "score": None,
            "status": "unverified",
            "explanation": (
                "Candidate education information is unavailable."
            ),
        }

    required_text = _normalise_text(requirements)
    candidate_text = _normalise_text(candidate_education)

    if not required_text or not candidate_text:
        return {
            "score": None,
            "status": "needs_review",
            "required": requirements,
            "candidate_education": candidate_education,
            "explanation": (
                "Education details could not be normalized reliably."
            ),
        }

    required_level = _degree_level(required_text)
    candidate_level = _degree_level(candidate_text)

    field_result = _field_match(
        required_text,
        candidate_text
    )

    if required_level and candidate_level:

        level_order = {
            "diploma": 1,
            "bachelor": 2,
            "master": 3,
            "doctorate": 4,
        }

        if level_order[candidate_level] >= level_order[required_level]:

            if field_result is True or field_result is None:
                return {
                    "score": 100.0,
                    "status": "matched",
                    "required": requirements,
                    "candidate_education": candidate_education,
                    "explanation": (
                        "The resume indicates a degree level that "
                        "meets the stated minimum; field equivalence "
                        "may still require human review."
                    ),
                }

            if field_result is False:
                return {
                    "score": None,
                    "status": "needs_review",
                    "required": requirements,
                    "candidate_education": candidate_education,
                    "explanation": (
                        "Degree level appears sufficient, but the "
                        "field of study differs and requires "
                        "human review."
                    ),
                }

        return {
            "score": 0.0,
            "status": "below_requirement",
            "required": requirements,
            "candidate_education": candidate_education,
            "explanation": (
                "The extracted degree level appears below the "
                "stated minimum; verify the original documents "
                "before making a decision."
            ),
        }

    return {
        "score": None,
        "status": "needs_review",
        "required": requirements,
        "candidate_education": candidate_education,
        "explanation": (
            "Education was found, but degree equivalence or "
            "field alignment is ambiguous and needs human review."
        ),
    }


# --------------------------------------------------
# 7. COMPONENT AGGREGATION
# --------------------------------------------------

def calculate_weighted_score(
    components: dict[str, dict],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Aggregate candidate component scores using evidence-aware weighting.

    Rules:
    1. Components marked not_required are excluded from evaluation.
    2. Components without sufficient evidence remain unevaluated.
    3. Evaluated components are normalized against applicable weight.
    4. Provisional scores are explicitly identified.
    5. Evaluation coverage is calculated only against applicable weight.
    """

    weights = (
        SCORING_WEIGHTS.copy()
        if weights is None
        else weights
    )

    validate_weights(weights)

    weighted_total = 0.0
    applicable_weight = 0.0
    evaluated_weight = 0.0

    breakdown = {}
    warnings = []

    for component, weight in weights.items():

        weight = float(weight)
        result = components.get(component) or {}

        status = result.get("status", "not_evaluated")

        # --------------------------------------------------
        # 1. EXCLUDE NON-APPLICABLE COMPONENTS
        # --------------------------------------------------

        if status == "not_required":

            breakdown[component] = {
                "score": None,
                "verified_score": None,
                "weight": weight,
                "contribution": None,
                "status": "not_required",
                "applicable": False,
            }

            continue

        applicable_weight += weight

        # --------------------------------------------------
        # 2. GET COMPONENT SCORE
        # --------------------------------------------------

        score = result.get("aggregation_score")

        if score is None:
            score = result.get("score")

        if score is None:

            breakdown[component] = {
                "score": None,
                "verified_score": result.get("score"),
                "weight": weight,
                "contribution": None,
                "status": status or "not_evaluated",
                "applicable": True,
            }

            warnings.append(
                f"{component} requires additional evidence."
            )

            continue

        # --------------------------------------------------
        # 3. VALIDATE SCORE
        # --------------------------------------------------

        try:
            score = clamp_score(score)

        except (TypeError, ValueError):

            breakdown[component] = {
                "score": None,
                "verified_score": None,
                "weight": weight,
                "contribution": None,
                "status": "needs_review",
                "applicable": True,
            }

            warnings.append(
                f"{component} produced an invalid score."
            )

            continue

        # --------------------------------------------------
        # 4. CALCULATE WEIGHTED CONTRIBUTION
        # --------------------------------------------------

        contribution = (
            score * weight / 100.0
        )

        weighted_total += contribution
        evaluated_weight += weight

        breakdown[component] = {
            "score": score,
            "verified_score": result.get("score"),
            "weight": weight,
            "contribution": round(contribution, 2),
            "status": "evaluated",
            "applicable": True,
        }

    # --------------------------------------------------
    # 5. CALCULATE APPLICABLE WEIGHT
    # --------------------------------------------------

    if applicable_weight <= 0:

        return {
            "score": None,
            "provisional_score": None,
            "evidence_adjusted_score": None,
            "weighted_contribution": 0.0,
            "breakdown": breakdown,
            "evaluated_weight": 0.0,
            "evidence_coverage": 0.0,
            "applicable_weight": 0.0,
            "available_weight": 0.0,
            "unevaluated_weight": 0.0,
            "not_applicable_weight": 100.0,
            "score_status": "insufficient_evidence",
            "warnings": [
                "No applicable scoring components were identified."
            ],
        }

    # --------------------------------------------------
    # 6. CALCULATE FINAL SCORE
    # --------------------------------------------------

    provisional_score = None

    if evaluated_weight > 0:

        provisional_score = clamp_score(
            weighted_total / evaluated_weight * 100
        )

    # --------------------------------------------------
    # 7. CALCULATE EVIDENCE COVERAGE
    # --------------------------------------------------

    evidence_coverage = round(
        evaluated_weight / applicable_weight * 100,
        2
    )

    unevaluated_weight = round(
        max(
            0.0,
            applicable_weight - evaluated_weight
        ),
        2
    )

    not_applicable_weight = round(
        max(
            0.0,
            100.0 - applicable_weight
        ),
        2
    )

    # --------------------------------------------------
    # 8. DETERMINE SCORE STATUS
    # --------------------------------------------------

    if evaluated_weight <= 0:

        score_status = "insufficient_evidence"

    elif unevaluated_weight <= 0.0001:

        score_status = "complete"

    else:

        score_status = "partial"

    # --------------------------------------------------
    # 9. RETURN TRANSPARENT SCORING REPORT
    # --------------------------------------------------

    return {
        "score": provisional_score,

        "provisional_score": (
            provisional_score
            if score_status == "partial"
            else None
        ),

        "evidence_adjusted_score": provisional_score,

        "weighted_contribution": round(
            weighted_total,
            2
        ),

        "breakdown": breakdown,

        "evaluated_weight": round(
            evaluated_weight,
            2
        ),

        "evidence_coverage": evidence_coverage,

        "applicable_weight": round(
            applicable_weight,
            2
        ),

        "available_weight": round(
            evaluated_weight,
            2
        ),

        "unevaluated_weight": unevaluated_weight,

        "not_applicable_weight": not_applicable_weight,

        "score_status": score_status,

        "warnings": warnings,
    }


# --------------------------------------------------
# 8. COMPLETE EXPLAINABLE SCORING ENGINE
# --------------------------------------------------

def score_candidate(
    jd: dict,
    profile: dict,
    matching_result: dict,
) -> dict[str, Any]:

    validate_weights()

    required_results = (
        matching_result.get("required_skill_analysis") or []
    )

    preferred_results = (
        matching_result.get("preferred_skill_analysis") or []
    )

    required_score = calculate_skill_score(
        required_results
    )

    preferred_score = calculate_skill_score(
        preferred_results
    )

    semantic_score = calculate_semantic_score(
        required_results,
        preferred_results,
    )

    experience_score = calculate_experience_score(
        jd,
        profile
    )

    education_score = calculate_education_score(
        jd,
        profile
    )

    components = {
        "required_skills": required_score,
        "semantic_relevance": semantic_score,
        "experience": experience_score,
        "education": education_score,
        "preferred_skills": preferred_score,
    }

    aggregation = calculate_weighted_score(
        components
    )

    # --------------------------------------------------
    # REQUIREMENT CLASSIFICATION
    # --------------------------------------------------

    missing_skills = [
        item.get("requirement")
        for item in required_results
        if item.get("status") == "missing"
    ]

    unverified_skills = [
        item.get("requirement")
        for item in required_results
        if item.get("status") == "unverified"
    ]

    related_skills = [
        item.get("requirement")
        for item in required_results
        if item.get("status") == "related_match"
    ]

    verification_skills = [
        item.get("requirement")
        for item in required_results
        if item.get("status") == "needs_verification"
    ]

    # --------------------------------------------------
    # EXPLANATIONS
    # --------------------------------------------------

    explanations = []

    for component, result in components.items():

        score = result.get("score")

        if score is None:
            explanations.append(
                f"{component}: not evaluated "
                f"({result.get('status', 'insufficient information')})."
            )

        else:
            explanations.append(
                f"{component}: {score}/100."
            )

    if aggregation["score_status"] == "partial":

        explanations.append(
            f"Provisional score only: "
            f"{aggregation['evaluated_weight']:.2f}% "
            f"of the scoring weight was evaluated; "
            f"{aggregation['unevaluated_weight']:.2f}% "
            f"remains unevaluated."
        )

    # --------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------

    return {
        "score": aggregation["score"],

        "provisional_score": aggregation["provisional_score"],

        "evidence_adjusted_score": aggregation[
            "evidence_adjusted_score"
        ],

        "score_status": aggregation["score_status"],

        "breakdown": aggregation["breakdown"],

        "evaluated_weight": aggregation["evaluated_weight"],

        "evidence_coverage": aggregation["evidence_coverage"],

        "unevaluated_weight": aggregation["unevaluated_weight"],

        "required_skill_analysis": required_results,

        "preferred_skill_analysis": preferred_results,

        "missing_skills": missing_skills,

        "unverified_skills": unverified_skills,

        "related_skills": related_skills,

        "skills_needing_verification": verification_skills,

        "experience_analysis": experience_score,

        "education_analysis": education_score,

        "semantic_analysis": semantic_score,

        "component_analysis": components,

        "explanations": explanations,

        "scoring_weights": SCORING_WEIGHTS.copy(),

        "method": "evidence_based_hybrid_weighted_scoring_v2",

        "ranking_warning": (
            "This is a provisional score. Review evidence coverage "
            "and unevaluated components before comparing candidates."
            if aggregation["score_status"] != "complete"
            else None
        ),
    }