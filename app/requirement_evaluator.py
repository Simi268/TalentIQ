"""
TalentIQ - Requirement Evidence Evaluator

Decomposes compound job requirements into independently
assessable skills while preserving their original wording.
"""

import re


COMPOUND_PATTERNS = [
    (
        r"\bverbal and written communication\b",
        ["verbal communication", "written communication"],
    ),
    (
        r"\borganizational and time-management skills\b",
        ["organizational skills", "time management"],
    ),
    (
        r"\binterpersonal skills and teamwork\b",
        ["interpersonal skills", "teamwork"],
    ),
    (
        r"\bproblem-solving and multitasking abilities\b",
        ["problem solving", "multitasking"],
    ),
    (
        r"\bms excel and google sheets\b",
        ["microsoft excel", "google sheets"],
    ),
    (
        r"\bresume screening and candidate evaluation\b",
        ["resume screening", "candidate evaluation"],
    ),
    (
        r"\brecruitment coordination and interview scheduling\b",
        ["recruitment coordination", "interview scheduling"],
    ),
]


def normalize_requirement(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def decompose_requirement(requirement: str) -> list[str]:
    """
    Convert a compound requirement into atomic requirements.

    Unknown requirements remain unchanged.
    """

    if not isinstance(requirement, str) or not requirement.strip():
        return []

    normalized = normalize_requirement(requirement)

    for pattern, components in COMPOUND_PATTERNS:
        if re.search(
    r"(?<![a-z])(?:" + pattern + r")(?![a-z])",
    normalized,
):
            return components.copy()

    return [normalized]


def decompose_requirements(
    requirements: list[str],
) -> list[str]:
    """Decompose and deduplicate a list of requirements."""

    output = []
    seen = set()

    for requirement in requirements or []:
        for component in decompose_requirement(requirement):

            normalized = normalize_requirement(component)

            if normalized and normalized not in seen:
                output.append(component)
                seen.add(normalized)

    return output


def evaluate_requirement_counts(results: list[dict]) -> dict:
    """Generate consistent requirement-level statistics."""

    counts = {
        "exact_match": 0,
        "related_match": 0,
        "needs_verification": 0,
        "unverified": 0,
        "missing": 0,
    }

    for result in results or []:
        status = result.get("status", "unverified")

        if status in counts:
            counts[status] += 1
        else:
            counts["unverified"] += 1

    counts["total"] = sum(counts.values())

    return counts