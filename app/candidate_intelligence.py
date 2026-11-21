"""Candidate comparison, ranking explanations, and offline ranking evaluation.

This module is deliberately independent of persistence and web routes. It accepts
the dictionaries already produced by TalentIQ's scoring/ranking pipeline.
It is decision-support only: it does not make hiring decisions.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite
from typing import Any, Iterable


def _number(value: Any, default: float = 0.0) -> float:
    """Convert a value to a finite float, otherwise return a safe default."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if isfinite(result) else default


def _candidate_id(candidate: dict[str, Any], fallback: int) -> Any:
    return candidate.get("id", candidate.get("candidate_id", fallback))


def _candidate_name(candidate: dict[str, Any], fallback: str) -> str:
    return (
        candidate.get("name")
        or candidate.get("candidate_name")
        or candidate.get("profile", {}).get("name")
        or fallback
    )


def _skills(candidate: dict[str, Any]) -> set[str]:
    """Read flat or structured skills and return normalized skill names."""
    profile = candidate.get("profile") or candidate
    raw = profile.get("skills") or []
    result: set[str] = set()

    if isinstance(raw, dict):
        raw = list(raw.keys())

    if not isinstance(raw, (list, tuple, set)):
        return result

    for item in raw:
        if isinstance(item, dict):
            name = item.get("name") or item.get("skill")
        else:
            name = item
        if name:
            result.add(str(name).strip().casefold())

    return result


def _explanation(candidate: dict[str, Any]) -> dict[str, Any]:
    value = candidate.get("explanation") or candidate.get("explanations") or {}
    return value if isinstance(value, dict) else {}


def _component_scores(candidate: dict[str, Any]) -> dict[str, float]:
    explanation = _explanation(candidate)
    breakdown = (
        candidate.get("breakdown")
        or explanation.get("score_breakdown")
        or candidate.get("score_breakdown")
        or {}
    )

    if not isinstance(breakdown, dict):
        return {}

    scores: dict[str, float] = {}
    for key, value in breakdown.items():
        if isinstance(value, dict):
            value = value.get("score")
        if value is None:
            continue
        scores[str(key)] = round(_number(value), 2)
    return scores


def _evidence(candidate: dict[str, Any]) -> dict[str, list[str]]:
    explanation = _explanation(candidate)
    matching = candidate.get("matching_result") or {}

    required_analysis = (
        explanation.get("required_skill_analysis")
        or candidate.get("required_skill_analysis")
        or matching.get("required_skill_analysis")
        or []
    )

    categories = {
        "matched": {},
        "related": {},
        "needs_verification": {},
        "missing": {},
    }

    priority = {
        "matched": 4,
        "related": 3,
        "needs_verification": 2,
        "missing": 1,
    }

    def add(category: str, requirement: Any) -> None:
        if not requirement:
            return

        name = str(requirement).strip()
        if not name:
            return

        key = " ".join(name.casefold().split())

        existing = next(
            (
                current_category
                for current_category, items in categories.items()
                if key in items
            ),
            None,
        )

        if existing is not None:
            if priority[existing] >= priority[category]:
                return
            del categories[existing][key]

        categories[category][key] = name

    if required_analysis:
        # Primary source: requirement-level analysis.
        for item in required_analysis:
            if not isinstance(item, dict):
                continue

            requirement = item.get("requirement") or item.get("skill")
            status = item.get("status")

            if status == "exact_match":
                add("matched", requirement)

            elif status == "related_match":
                add("related", requirement)

            elif status in {"needs_verification", "uncertain"}:
                add("needs_verification", requirement)

            elif status in {"unverified", "missing"}:
                add("missing", requirement)

    else:
        # Fallback only when requirement-level analysis is unavailable.
        for item in explanation.get("satisfied", []) or []:
            add("matched", item)

        for item in explanation.get("related_skills", []) or []:
            add("related", item)

        for item in explanation.get("verify_in_interview", []) or []:
            add("needs_verification", item)

        for item in explanation.get("not_verified", []) or []:
            add("missing", item)

    return {
        category: sorted(items.values(), key=str.casefold)
        for category, items in categories.items()
    }

    


def compare_candidates(
    candidates: list[dict[str, Any]],
    candidate_ids: list[Any] | None = None,
) -> dict[str, Any]:
    """Build a side-by-side comparison for selected candidates."""

    if not isinstance(candidates, list):
        raise TypeError("candidates must be a list")

    selected = []
    requested = set(candidate_ids) if candidate_ids is not None else None

    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue

        identifier = _candidate_id(candidate, index)

        if requested is None or identifier in requested:
            selected.append((index, candidate))

    if requested is not None:
        found = {_candidate_id(item, index) for index, item in selected}
        missing_ids = [
            value for value in candidate_ids if value not in found
        ]
    else:
        missing_ids = []

    rows = []
    all_skill_names: set[str] = set()

    for index, candidate in selected:
        identifier = _candidate_id(candidate, index)
        name = _candidate_name(candidate, f"Candidate {index + 1}")

        profile = candidate.get("profile") or candidate
        explanation = candidate.get("explanation") or {}

        skills = _skills(candidate)
        all_skill_names.update(skills)

        # Experience: prefer professional experience, then internship.
        professional = profile.get("professional_experience_years")
        internship = profile.get("internship_experience_years")
        relevant = profile.get("relevant_experience_years")
        total = profile.get("total_experience_years")

        experience = next(
            (
                value for value in (relevant, professional, internship, total)
                if value is not None
            ),
            None,
        )

        try:
            experience_value = (
                round(float(experience), 2)
                if experience is not None and isfinite(float(experience))
                else None
            )
        except (TypeError, ValueError):
            experience_value = None

        # Score
        score = candidate.get(
            "score",
            candidate.get("overall_score", candidate.get("match_score")),
        )

        score_value = _number(score, default=float("nan"))

        if not isfinite(score_value):
            score_value = None

        # Evaluation status
        score_status = (
            candidate.get("score_status")
            or explanation.get("score_status")
            or "unknown"
        )

        # Evidence coverage
        evidence_coverage = candidate.get(
            "evidence_coverage",
            explanation.get(
                "evidence_coverage",
                explanation.get("evaluated_weight"),
            ),
        )

        try:
            evidence_coverage = (
                round(float(evidence_coverage), 2)
                if evidence_coverage is not None
                else None
            )
        except (TypeError, ValueError):
            evidence_coverage = None

        # Unevaluated scoring weight
        unevaluated_weight = candidate.get(
            "unevaluated_weight",
            explanation.get("unevaluated_weight"),
        )

        rows.append({
            "candidate_id": identifier,
            "name": name,
            "score": round(score_value, 2) if score_value is not None else None,
            "rank": candidate.get("rank"),
            "score_status": score_status,
            "evidence_coverage": evidence_coverage,
            "unevaluated_weight": unevaluated_weight,
            "experience_years": experience_value,
            "professional_experience_years": professional,
            "internship_experience_years": internship,
            "skills": sorted(skills),
            "component_scores": _component_scores(candidate),
            "evidence": _evidence(candidate),
        })

    skill_matrix = []

    for skill in sorted(all_skill_names):
        skill_matrix.append({
            "skill": skill,
            "candidates": {
                row["candidate_id"]: skill in row["skills"]
                for row in rows
            },
        })

    return {
        "candidate_count": len(rows),
        "candidates": rows,
        "skill_matrix": skill_matrix,
        "missing_candidate_ids": missing_ids,
        "comparison_note": (
            "Comparison summarizes extracted evidence and model scores. "
            "Verify important claims with the candidate; it is not an "
            "automated hiring decision."
        ),
    }


def explain_ranking(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Explain score differences using available score components.

    This is descriptive, not causal: it reports observed score differences
    and does not claim that a component caused a rank.
    """
    valid = [
        item for item in candidates
        if isinstance(item, dict)
    ]

    def score_of(item: dict[str, Any]) -> float:
        return _number(
            item.get("score", item.get("overall_score", item.get("match_score"))),
            default=float("-inf"),
        )

    ordered = sorted(valid, key=score_of, reverse=True)
    explanations = []

    for position, candidate in enumerate(ordered, start=1):
        score = score_of(candidate)
        name = _candidate_name(candidate, f"Candidate {position}")
        components = _component_scores(candidate)
        evidence = _evidence(candidate)

        if position == 1:
            comparison = "Highest score in this candidate set."
            score_gap = 0.0
        else:
            previous = ordered[position - 2]
            previous_score = score_of(previous)
            gap = previous_score - score
            score_gap = round(gap, 2) if isfinite(gap) else None
            comparison = (
                f"{score_gap:.2f} points below the candidate ranked "
                f"immediately above."
                if score_gap is not None
                else "Could not calculate the score difference."
            )

        explanations.append({
            "candidate_id": _candidate_id(candidate, position - 1),
            "name": name,
            "rank": position,
            "score": round(score, 2) if isfinite(score) else None,
            "comparison_to_previous": comparison,
            "score_gap_to_previous": score_gap,
            "component_scores": components,
            "evidence_summary": {
                key: len(value) for key, value in evidence.items()
            },
            "interpretation": (
                "Review component scores and supporting resume evidence. "
                "A higher aggregate score is not proof of overall candidate "
                "quality or future job performance."
            ),
        })

    return explanations


def evaluate_ranking(
    ranked_candidate_ids: list[Any],
    relevant_candidate_ids: set[Any] | list[Any] | tuple[Any, ...],
    k: int | None = None,
) -> dict[str, Any]:
    """Evaluate a ranking against a labelled relevant-candidate set.

    Metrics:
    - precision_at_k: relevant items in the first k divided by k (or list size)
    - recall_at_k: relevant items in the first k divided by all labelled relevant
    - reciprocal_rank: reciprocal position of the first relevant result
    - average_precision: mean precision at each relevant result's rank
    - ndcg_at_k: binary-relevance normalized discounted cumulative gain

    This function requires labelled evaluation data. It must not be used to
    claim model quality when labels are absent or created from model scores.
    """
    ranked = list(ranked_candidate_ids or [])
    relevant = set(relevant_candidate_ids or [])

    if k is None:
        cutoff = len(ranked)
    else:
        if not isinstance(k, int) or k < 1:
            raise ValueError("k must be a positive integer.")
        cutoff = min(k, len(ranked))

    if not relevant:
        return {
            "evaluated": False,
            "reason": "No labelled relevant candidates were supplied.",
            "precision_at_k": None,
            "recall_at_k": None,
            "reciprocal_rank": None,
            "average_precision": None,
            "ndcg_at_k": None,
            "k": cutoff,
        }

    top = ranked[:cutoff]
    hits = [1 if candidate_id in relevant else 0 for candidate_id in top]
    relevant_found = sum(hits)

    precision = relevant_found / cutoff if cutoff else 0.0
    recall = relevant_found / len(relevant)

    first_relevant_rank = next(
        (index for index, hit in enumerate(hits, start=1) if hit),
        None,
    )
    reciprocal_rank = (
        1 / first_relevant_rank if first_relevant_rank else 0.0
    )

    precisions_at_hits = []
    running_hits = 0
    for rank, hit in enumerate(hits, start=1):
        running_hits += hit
        if hit:
            precisions_at_hits.append(running_hits / rank)

    average_precision = (
        sum(precisions_at_hits) / min(len(relevant), cutoff)
        if cutoff and min(len(relevant), cutoff) > 0
        else 0.0
    )

    # Use the standard binary relevance discount: log2(rank + 1).
    import math
    dcg = sum(
        hit / math.log2(rank + 1)
        for rank, hit in enumerate(hits, start=1)
    )
    ideal_hits = min(len(relevant), cutoff)
    idcg = sum(
        1 / math.log2(rank + 1)
        for rank in range(1, ideal_hits + 1)
    )
    ndcg = dcg / idcg if idcg else 0.0

    return {
        "evaluated": True,
        "reason": None,
        "precision_at_k": round(precision, 4),
        "recall_at_k": round(recall, 4),
        "reciprocal_rank": round(reciprocal_rank, 4),
        "average_precision": round(average_precision, 4),
        "ndcg_at_k": round(ndcg, 4),
        "k": cutoff,
        "relevant_found": relevant_found,
        "labelled_relevant_count": len(relevant),
    }
