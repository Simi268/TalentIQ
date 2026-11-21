"""
TalentIQ Candidate Ranking Engine

Features:
- Evidence-aware candidate ranking
- Provisional score support
- Safe handling of unevaluated candidates
- Evidence coverage tie-breaking
- Candidate filtering
- Candidate comparison
- Ranking summary analytics

Important:
An unevaluated candidate is not automatically a zero-score candidate.
"""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------
# SCORE RESOLUTION
# ---------------------------------------------------------

SCORE_KEYS = (
    "provisional_score",
    "overall_score",
    "final_score",
    "weighted_score",
    "total_score",
    "score",
)


def _to_score(value: Any) -> float | None:

    if value is None or isinstance(value, bool):
        return None

    try:
        score = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(score):
        return None

    return max(0.0, min(100.0, score))


def _extract_score(data: Any) -> float | None:

    if not isinstance(data, dict):
        return None

    for key in SCORE_KEYS:

        if key not in data:
            continue

        score = _to_score(data.get(key))

        if score is not None:
            return score

    return None


def _get_candidate_score(candidate: dict) -> float | None:
    """
    Resolve the best available candidate score.

    Provisional score takes precedence over persisted score.
    """

    if not isinstance(candidate, dict):
        return None

    score = _extract_score(candidate)

    if score is not None:
        return score

    for key in (
        "scoring",
        "explanation",
        "evaluation",
        "result",
    ):

        score = _extract_score(candidate.get(key))

        if score is not None:
            return score

    explanation = candidate.get("explanation")

    if isinstance(explanation, dict):

        for key in (
            "scoring",
            "result",
            "score_analysis",
        ):

            score = _extract_score(explanation.get(key))

            if score is not None:
                return score

    return None


# ---------------------------------------------------------
# CANDIDATE HELPERS
# ---------------------------------------------------------

def _get_candidate_id(candidate: dict):

    for key in (
        "id",
        "candidate_id",
        "resume_id",
        "uuid",
    ):

        value = candidate.get(key)

        if value is not None:
            return value

    return None


def _get_candidate_name(candidate: dict) -> str:

    for key in (
        "name",
        "candidate_name",
        "full_name",
    ):

        if candidate.get(key):
            return str(candidate[key])

    profile = candidate.get("profile")

    if isinstance(profile, dict):

        for key in (
            "name",
            "candidate_name",
            "full_name",
        ):

            if profile.get(key):
                return str(profile[key])

    return "Unknown candidate"


def _as_list(value):

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, (tuple, set)):
        return list(value)

    return [value]


def _get_skill_names(candidate: dict) -> set[str]:

    values = []

    for key in (
        "skills",
        "matched_skills",
        "satisfied",
        "related_skills",
    ):

        values.extend(_as_list(candidate.get(key)))

    profile = candidate.get("profile")

    if isinstance(profile, dict):

        values.extend(_as_list(profile.get("skills")))

        intelligence = profile.get("intelligence")

        if isinstance(intelligence, dict):
            values.extend(
                _as_list(intelligence.get("skills"))
            )

    explanation = candidate.get("explanation")

    if isinstance(explanation, dict):

        for key in (
            "satisfied",
            "related_skills",
            "matched_skills",
        ):

            values.extend(
                _as_list(explanation.get(key))
            )

    skills = set()

    for item in values:

        if isinstance(item, dict):

            item = (
                item.get("canonical")
                or item.get("name")
                or item.get("skill")
                or item.get("skill_name")
            )

        if isinstance(item, str) and item.strip():

            skills.add(item.strip().casefold())

    return skills


def _get_experience(candidate: dict) -> float | None:

    values = [
        candidate.get("relevant_experience_years"),
        candidate.get("experience_years"),
        candidate.get("total_experience_years"),
        candidate.get("experience"),
    ]

    profile = candidate.get("profile")

    if isinstance(profile, dict):

        values.extend([
            profile.get("relevant_experience_years"),
            profile.get("experience_years"),
            profile.get("total_experience_years"),
            
        ])

        experience = profile.get("experience")

        if isinstance(experience, dict):

            values.extend([
                experience.get("relevant_experience_years"),
                experience.get("total_experience_years"),
                experience.get("years"),
            ])

    for value in values:

        if value is None or isinstance(value, bool):
            continue

        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            continue

        if math.isfinite(number) and number >= 0:
            return number

    return None


# ---------------------------------------------------------
# CANDIDATE RANKING
# ---------------------------------------------------------

def rank_candidates(
    candidates,
    top_n=None,
    min_score=None,
):
    """
    Rank candidates by:

    1. Available match score
    2. Evidence coverage
    3. Original input order for stable ties

    Unscored candidates remain at the bottom unless min_score
    is provided, in which case they are excluded.
    """

    rows = list(candidates or [])

    if top_n is not None:

        if (
            isinstance(top_n, bool)
            or not isinstance(top_n, int)
            or top_n <= 0
        ):

            raise ValueError(
                "top_n must be a non-negative integer or None"
            )

    threshold = None

    if min_score is not None:

        threshold = _to_score(min_score)

        if threshold is None:

            raise ValueError(
                "min_score must be between 0 and 100"
            )

    decorated = []

    for index, candidate in enumerate(rows):

        if not isinstance(candidate, dict):
            continue

        score = _get_candidate_score(candidate)

        if threshold is not None:

            if score is None or score < threshold:
                continue

        coverage = candidate.get(
            "evidence_coverage",
            candidate.get("evaluated_weight", -1),
        )

        try:
            coverage = float(coverage)

            if not math.isfinite(coverage):
                coverage = -1

        except (TypeError, ValueError, OverflowError):
            coverage = -1

        decorated.append(
            (
                candidate,
                score,
                coverage,
                index,
            )
        )

    decorated.sort(
        key=lambda item: (
            item[1] is not None,
            item[1] if item[1] is not None else -1,
            item[2],
            -item[3],
        ),
        reverse=True,
    )

    ranked = []
    for position, item in enumerate(decorated, start=1):
        candidate = dict(item[0])
        candidate["rank"] = position
        ranked.append(candidate)

    if top_n is not None:
        ranked = ranked[:top_n]

    return ranked


# ---------------------------------------------------------
# CANDIDATE FILTERING
# ---------------------------------------------------------

def filter_candidates(
    candidates,
    min_score=None,
    required_skills=None,
    min_experience=None,
    max_score=None,
):
    """
    Filter candidates using:

    - Minimum match score
    - Required skill evidence
    - Minimum known experience

    Unknown experience does not satisfy an experience filter.
    """

    rows = list(candidates or [])

    threshold = None

    if min_score is not None:

        threshold = _to_score(min_score)

        if threshold is None:

            raise ValueError(
                "min_score must be between 0 and 100"
            )

    maximum = None

    if max_score is not None:

        maximum = _to_score(max_score)

        if maximum is None:

            raise ValueError(
                "max_score must be between 0 and 100"
            )

    if (
        threshold is not None
        and maximum is not None
        and threshold > maximum
    ):

        raise ValueError(
            "min_score cannot exceed max_score"
        )

    experience_threshold = None

    if min_experience is not None:

        try:
            experience_threshold = float(min_experience)

        except (TypeError, ValueError, OverflowError):

            raise ValueError(
                "min_experience must be non-negative"
            )

        if (
            not math.isfinite(experience_threshold)
            or experience_threshold < 0
        ):

            raise ValueError(
                "min_experience must be non-negative"
            )

    requested_skills = {
        skill.strip().casefold()
        for skill in (required_skills or [])
        if isinstance(skill, str) and skill.strip()
    }

    filtered = []

    for candidate in rows:

        if not isinstance(candidate, dict):
            continue

        score = _get_candidate_score(candidate)

        if threshold is not None:

            if score is None or score < threshold:
                continue

        if maximum is not None:

            if score is None or score > maximum:
                continue

        if requested_skills:

            available = _get_skill_names(candidate)

            if not requested_skills.issubset(available):
                continue

        if experience_threshold is not None:

            experience = _get_experience(candidate)

            if (
                experience is None
                or experience < experience_threshold
            ):

                continue

        filtered.append(dict(candidate))

    return rank_candidates(filtered)


# ---------------------------------------------------------
# CANDIDATE COMPARISON
# ---------------------------------------------------------

def compare_candidates(candidates, fields=None):
    """
    Generate side-by-side candidate comparison data.

    Preserves scoring evidence and separates professional
    experience from internship experience.

    Evidence categories are mutually exclusive:
    matched > related > needs_verification > missing.
    """

    rows = rank_candidates(candidates)

    if len(rows) < 2:
        raise ValueError(
            "At least two candidates are required for comparison"
        )

    comparison = []

    default_fields = [
        "id",
        "name",
        "score",
        "overall_score",
        "score_status",
        "evidence_coverage",
        "experience",
        "experience_years",
        "professional_experience_years",
        "internship_experience_years",
        "stated_experience_years",
        "skills",
        "education",
        "matched_skills",
        "missing_skills",
        "component_scores",
        "evidence",
    ]

    selected_fields = fields or default_fields

    for candidate in rows:

        profile = candidate.get("profile") or {}
        explanation = candidate.get("explanation") or {}
        scoring = candidate.get("scoring") or {}

        if not isinstance(profile, dict):
            profile = {}

        if not isinstance(explanation, dict):
            explanation = {}

        if not isinstance(scoring, dict):
            scoring = {}

        score = _get_candidate_score(candidate)

        score_status = (
            candidate.get("score_status")
            or explanation.get("score_status")
            or scoring.get("score_status")
        )

        evidence_coverage = candidate.get("evidence_coverage")

        if evidence_coverage is None:
            evidence_coverage = explanation.get("evidence_coverage")

        if evidence_coverage is None:
            evidence_coverage = scoring.get("evidence_coverage")

        professional_years = profile.get(
            "professional_experience_years"
        )

        internship_years = profile.get(
            "internship_experience_years"
        )

        stated_years = profile.get(
            "stated_experience_years"
        )

        required_analysis = (
            explanation.get("required_skill_analysis")
            or candidate.get("required_skill_analysis")
            or (
                candidate.get("matching_result") or {}
            ).get("required_skill_analysis")
            or []
        )

        evidence = {
            "matched": [],
            "related": [],
            "needs_verification": [],
            "missing": [],
        }

        # -------------------------------------------------
        # PRIMARY SOURCE: REQUIREMENT-LEVEL ANALYSIS
        # -------------------------------------------------

        if isinstance(required_analysis, list) and required_analysis:

            for item in required_analysis:

                if not isinstance(item, dict):
                    continue

                requirement = (
                    item.get("requirement")
                    or item.get("skill")
                )

                if not requirement:
                    continue

                requirement = str(requirement).strip()

                if not requirement:
                    continue

                status = str(item.get("status", "")).lower().strip()

                if status == "exact_match":
                    category = "matched"

                elif status == "related_match":
                    category = "related"

                elif status in (
                    "needs_verification",
                    "unverified",
                    "uncertain",
                ):
                    category = "needs_verification"

                elif status == "missing":
                    category = "missing"

                else:
                    continue

                evidence[category].append(requirement)

        # -------------------------------------------------
        # FALLBACK: LEGACY EXPLANATION DATA
        # -------------------------------------------------

        else:

            evidence["matched"] = _as_list(
                explanation.get("satisfied")
            )

            evidence["related"] = _as_list(
                explanation.get("related_skills")
            )

            evidence["needs_verification"] = _as_list(
                explanation.get("not_verified")
            )

            evidence["missing"] = _as_list(
                explanation.get("missing_skills")
            )

        # -------------------------------------------------
        # NORMALIZE AND REMOVE DUPLICATE CLASSIFICATIONS
        # -------------------------------------------------

        priority = [
            "matched",
            "related",
            "needs_verification",
            "missing",
        ]

        seen = set()

        for category in priority:

            unique_items = []

            for item in evidence[category]:

                if isinstance(item, dict):
                    item = (
                        item.get("requirement")
                        or item.get("canonical")
                        or item.get("name")
                        or item.get("skill")
                    )

                if not isinstance(item, str):
                    continue

                item = item.strip()

                if not item:
                    continue

                normalized = item.casefold()

                if normalized in seen:
                    continue

                seen.add(normalized)
                unique_items.append(item)

            evidence[category] = sorted(
                unique_items,
                key=str.casefold
            )

        # -------------------------------------------------
        # COMPARISON DATA
        # -------------------------------------------------

        data = {
            "id": _get_candidate_id(candidate),

            "name": _get_candidate_name(candidate),

            "score": score,
            "overall_score": score,

            "score_status": score_status,
            "evidence_coverage": evidence_coverage,

            "experience": _get_experience(candidate),
            "experience_years": _get_experience(candidate),

            "professional_experience_years": professional_years,
            "internship_experience_years": internship_years,
            "stated_experience_years": stated_years,

            "skills": sorted(
                _get_skill_names(candidate)
            ),

            "education": (
                candidate.get("education")
                or profile.get("education")
                or profile.get("education_summary")
            ),

            "matched_skills": evidence["matched"],

            "missing_skills": evidence["missing"],

            "component_scores": (
                candidate.get("component_scores")
                or explanation.get("component_analysis")
                or {}
            ),

            "evidence": evidence,

            "missing": evidence["missing"],
        }

        comparison.append({
            key: data.get(key)
            for key in selected_fields
        })

    return {
        "candidate_count": len(comparison),
        "candidates": comparison,
    }


# ---------------------------------------------------------
# RANKING ANALYTICS
# ---------------------------------------------------------

def generate_ranking_summary(candidates):
    """
    Summarize the current candidate pool.

    Unevaluated candidates are reported separately and are
    not included in average or score-distribution calculations.
    """

    rows = [
        candidate
        for candidate in (candidates or [])
        if isinstance(candidate, dict)
    ]

    evaluated = []

    for candidate in rows:

        score = _get_candidate_score(candidate)

        if score is not None:
            evaluated.append((candidate, score))

    unscored_count = len(rows) - len(evaluated)

    scores = [
        score
        for _, score in evaluated
    ]

    ranked = rank_candidates([
        candidate
        for candidate, _ in evaluated
    ])

    average = (
        sum(scores) / len(scores)
        if scores
        else None
    )

    top = ranked[0] if ranked else None

    return {

        "total_candidates": len(rows),

        "evaluated_candidates": len(evaluated),

        "unevaluated_candidates": unscored_count,

        "average_score": (
            round(average, 2)
            if average is not None
            else None
        ),

        "highest_score": (
            max(scores)
            if scores
            else None
        ),

        "lowest_score": (
            min(scores)
            if scores
            else None
        ),

        "top_candidate": (
            {
                "id": _get_candidate_id(top),
                "name": _get_candidate_name(top),
                "score": _get_candidate_score(top),
            }
            if top
            else None
        ),

        "score_distribution": {

            "90-100": sum(
                90 <= score <= 100
                for score in scores
            ),

            "80-89": sum(
                80 <= score < 90
                for score in scores
            ),

            "70-79": sum(
                70 <= score < 80
                for score in scores
            ),

            "60-69": sum(
                60 <= score < 70
                for score in scores
            ),

            "below-60": sum(
                score < 60
                for score in scores
            ),

            "unscored": unscored_count,

        },

    }