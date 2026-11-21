"""Quality and safety checks for TalentIQ's document-processing pipeline.

These checks do not make hiring decisions and do not change candidate scores.
They validate uploads, identify extraction gaps, and sanity-check score payloads.
"""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
DEFAULT_MAX_FILE_BYTES = 8 * 1024 * 1024


def validate_upload(
    filename: str,
    content: bytes,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> dict[str, Any]:
    """Validate an uploaded file before parsing it.

    Returns a stable result dictionary. Invalid uploads are rejected by callers
    when ``valid`` is False; warnings are non-fatal and should be shown/logged.
    """
    errors: list[str] = []
    warnings: list[str] = []

    safe_name = Path(str(filename or "")).name
    extension = Path(safe_name).suffix.lower()
    payload = content if isinstance(content, bytes) else b""

    if not safe_name or safe_name in {".", ".."}:
        errors.append("A valid filename is required.")

    if extension not in SUPPORTED_EXTENSIONS:
        errors.append("Only PDF, DOCX and TXT files are supported.")

    if not payload:
        errors.append("The uploaded file is empty.")

    if max_file_bytes <= 0:
        errors.append("The configured maximum file size must be positive.")
    elif len(payload) > max_file_bytes:
        errors.append(
            f"File exceeds the {max_file_bytes}-byte upload limit."
        )

    if safe_name != str(filename or ""):
        warnings.append("The uploaded filename contained a path; only its basename is used.")

    if extension == ".pdf" and payload and not payload.startswith(b"%PDF"):
        errors.append("The file does not appear to be a valid PDF.")

    if extension == ".docx" and payload and not payload.startswith(b"PK"):
        errors.append("The file does not appear to be a valid DOCX archive.")

    return {
        "valid": not errors,
        "filename": safe_name,
        "extension": extension,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest() if payload else None,
        "errors": errors,
        "warnings": warnings,
    }


def assess_extracted_text(text: str, filename: str = "") -> dict[str, Any]:
    """Detect likely extraction problems without guessing missing resume facts."""
    value = text if isinstance(text, str) else ""
    normalized = re.sub(r"\s+", " ", value).strip()
    warnings: list[str] = []
    errors: list[str] = []

    if not normalized:
        errors.append("No text could be extracted from this document.")
    elif len(normalized) < 80:
        warnings.append(
            "Very little text was extracted; the document may be scanned, "
            "image-based, or poorly formatted."
        )

    replacement_count = value.count("\ufffd")
    if replacement_count:
        warnings.append(
            f"Text extraction contains {replacement_count} replacement characters."
        )

    printable = sum(ch.isprintable() or ch.isspace() for ch in value)
    if value and printable / max(len(value), 1) < 0.85:
        warnings.append("The extracted text contains an unusually high proportion of non-printable characters.")

    return {
        "ok": not errors,
        "filename": Path(filename).name if filename else None,
        "character_count": len(value),
        "word_count": len(normalized.split()) if normalized else 0,
        "warnings": warnings,
        "errors": errors,
    }


def assess_resume_profile(
    profile: dict[str, Any],
    extracted_text: str = "",
) -> dict[str, Any]:
    """Report evidence coverage and extraction warnings for a parsed resume.

    Missing contact details are not errors. They are common and must not
    influence candidate suitability or ranking.
    """
    profile = profile if isinstance(profile, dict) else {}
    warnings: list[str] = []
    review_items: list[str] = []

    raw_skills = profile.get("skills") or []
    if isinstance(raw_skills, list):
        skill_count = len(raw_skills)
    else:
        skill_count = 0
        warnings.append("Skills field has an unexpected format.")

    experience_evidence = profile.get("experience_evidence") or []
    project_evidence = profile.get("project_evidence") or profile.get("projects") or []
    education = profile.get("education")

    if skill_count == 0:
        review_items.append("No skills were confidently extracted.")
    if not experience_evidence:
        review_items.append("No employment experience evidence was extracted.")
    if not project_evidence:
        review_items.append("No project evidence was extracted.")
    if not education:
        review_items.append("Education information was not found.")

    years = profile.get("relevant_experience_years")
    if years is not None:
        try:
            numeric_years = float(years)
            if not math.isfinite(numeric_years) or numeric_years < 0:
                warnings.append("Relevant experience value is invalid.")
            elif numeric_years > 50:
                warnings.append("Relevant experience exceeds 50 years; verify extraction.")
        except (TypeError, ValueError):
            warnings.append("Relevant experience is not numeric.")

    text_quality = assess_extracted_text(extracted_text) if extracted_text else None
    if text_quality and text_quality["errors"]:
        warnings.extend(text_quality["errors"])
    elif text_quality:
        warnings.extend(text_quality["warnings"])

    # Contact details are deliberately informational only.
    contact = {
        "email_present": bool(profile.get("email")),
        "phone_present": bool(profile.get("phone")),
    }

    return {
        "quality_status": (
            "needs_review" if warnings or review_items else "ok"
        ),
        "skill_count": skill_count,
        "contact": contact,
        "review_items": review_items,
        "warnings": list(dict.fromkeys(warnings)),
        "text_quality": text_quality,
    }


def validate_score_result(result: dict[str, Any]) -> dict[str, Any]:
    """Sanity-check a scoring payload; never silently repair a score."""
    result = result if isinstance(result, dict) else {}
    errors: list[str] = []
    warnings: list[str] = []

    score = result.get("score")
    try:
        numeric_score = float(score)
        if not math.isfinite(numeric_score):
            errors.append("Overall score must be a finite number.")
        elif not 0 <= numeric_score <= 100:
            errors.append("Overall score must be between 0 and 100.")
    except (TypeError, ValueError):
        errors.append("Overall score is missing or not numeric.")

    breakdown = result.get("breakdown") or {}
    if not isinstance(breakdown, dict):
        errors.append("Score breakdown must be an object.")
        breakdown = {}

    for component, value in breakdown.items():
        component_score = value.get("score") if isinstance(value, dict) else value
        try:
            number = float(component_score)
            if not math.isfinite(number) or not 0 <= number <= 100:
                errors.append(
                    f"Breakdown component '{component}' must be between 0 and 100."
                )
        except (TypeError, ValueError):
            errors.append(
                f"Breakdown component '{component}' is missing or not numeric."
            )

    weights = result.get("weights")
    if isinstance(weights, dict) and weights:
        try:
            total_weight = sum(float(value) for value in weights.values())
            if any(float(value) < 0 for value in weights.values()):
                errors.append("Scoring weights cannot be negative.")
            if not math.isclose(total_weight, 1.0, abs_tol=0.02):
                warnings.append(
                    f"Scoring weights sum to {total_weight:.3f}, not approximately 1.0."
                )
        except (TypeError, ValueError):
            errors.append("Scoring weights must be numeric.")

    if not breakdown:
        warnings.append("No component breakdown was supplied.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }
