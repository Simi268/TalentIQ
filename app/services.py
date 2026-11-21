"""TalentIQ integration layer.

Connects document parsing, resume intelligence, JD intelligence,
semantic matching, explainable scoring and candidate ranking.
"""

import io
import re
from pathlib import Path

import fitz
from docx import Document

from app.resume_intelligence import (
    extract_resume_intelligence,
    SKILL_ALIASES,
)
from app.jd_intelligence import analyze_jd as analyze_jd_engine
from app.semantic_matching import (
    match_candidate,
    calculate_semantic_similarity,
)
from app.scoring_engine import (
    score_candidate as calculate_candidate_score,
)
from app.ranking_engine import (
    rank_candidates as engine_rank_candidates,
)
import logging
from app.requirement_evaluator import decompose_requirements
from app.requirement_evaluator import decompose_requirements

logger = logging.getLogger(__name__)


# --------------------------------------------------
# 1. SKILL NORMALIZATION
# --------------------------------------------------

def normalize_skills(text: str) -> list[str]:
    """Normalize skill aliases into canonical skill names."""

    if not isinstance(text, str) or not text.strip():
        return []

    normalized = []

    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            pattern = (
                r"(?<![a-z0-9+#])"
                + re.escape(alias.lower())
                + r"(?![a-z0-9+#])"
            )

            if re.search(pattern, text.lower()):
                normalized.append(canonical)
                break

    return sorted(set(normalized))


# --------------------------------------------------
# 2. DOCUMENT PARSING
# --------------------------------------------------

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def parse_document(filename: str, content: bytes) -> str:
    """Extract text from PDF, DOCX or TXT documents."""

    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Only PDF, DOCX and TXT documents are supported."
        )

    if extension == ".txt":
        return content.decode("utf-8", errors="replace")

    if extension == ".pdf":
        try:
            with fitz.open(
                stream=content,
                filetype="pdf",
            ) as document:
                return "\n".join(
                    page.get_text("text")
                    for page in document
                )

        except Exception as exc:
            raise ValueError(
                f"Could not read PDF: {exc}"
            ) from exc

    if extension == ".docx":
        try:
            document = Document(io.BytesIO(content))

            paragraphs = [
                paragraph.text
                for paragraph in document.paragraphs
            ]

            # Include table content.
            for table in document.tables:
                for row in table.rows:
                    paragraphs.append(
                        " | ".join(
                            cell.text for cell in row.cells
                        )
                    )

            return "\n".join(paragraphs)

        except Exception as exc:
            raise ValueError(
                f"Could not read DOCX: {exc}"
            ) from exc

    raise ValueError("Unsupported document format.")


# --------------------------------------------------
# 3. JOB DESCRIPTION ANALYSIS
# --------------------------------------------------

def analyze_jd(description: str) -> dict:
    """Analyze a JD using Groq with deterministic fallback."""

    if not isinstance(description, str) or not description.strip():
        raise ValueError("Job description cannot be empty.")

    # Always run the deterministic parser first.
    result = analyze_jd_engine(description)

    result["title"] = (
        result.get("job_title") or "Untitled role"
    )

    # Preserve existing experience compatibility.
    if result.get("minimum_experience") is None:
        match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*\+?\s*years?"
            r"\s+(?:of\s+)?experience\b",
            description,
            re.IGNORECASE,
        )

        if match:
            result["minimum_experience"] = float(
                match.group(1)
            )

    # Default provider: deterministic parser.
    result["analysis_provider"] = "python_fallback"

    try:
        from app.llm_service import extract_jd_with_llm

        llm_result = extract_jd_with_llm(description)
        print("\n========== GROQ RAW EXTRACTION ==========")
        print(llm_result)
        print("=========================================\n")
        logger.info(
            "GROQ RAW JD EXTRACTION: %s",
            llm_result)

                # Validate skills against the original JD text.
        source_text = " ".join(description.casefold().split())

        source_skills = set(normalize_skills(description))

        def validated_skills(skills):
            validated = set()

            for skill in skills:
                if not isinstance(skill, str):
                    continue

                candidate = " ".join(
                    skill.casefold().split()
                )

                if not candidate or candidate not in source_text:
                    continue

                canonical = normalize_skills(skill)

                if canonical:
                    validated.update(canonical)
                else:
                    validated.add(candidate)

            return validated

        llm_required = validated_skills(
            llm_result.get("required_skills", [])
        )

        llm_preferred = validated_skills(
            llm_result.get("preferred_skills", [])
        )

        llm_unclassified = validated_skills(
            llm_result.get("unclassified_skills", [])
        )

        # Prevent classification conflicts.
        llm_preferred -= llm_required
        llm_unclassified -= llm_required | llm_preferred

        # Preserve existing classifications when Groq
        # does not classify a detected skill.
        original_required = set(
            result.get("required_skills", [])
        )
        original_preferred = set(
            result.get("preferred_skills", [])
        )
        original_unclassified = set(
            result.get("unclassified_skills", [])
        )

        classified = (
            llm_required
            | llm_preferred
            | llm_unclassified
        )

        remaining = source_skills - classified

        result["required_skills"] = sorted(
            llm_required | (original_required & remaining)
        )

        result["preferred_skills"] = sorted(
            llm_preferred | (original_preferred & remaining)
        )

        result["unclassified_skills"] = sorted(
            llm_unclassified | (original_unclassified & remaining)
        )

        result["all_skills"] = sorted(source_skills)

        # Validate extracted information against source text.
        source = " ".join(description.lower().split())

        def supported_items(items):
            accepted = []

            for item in items:
                if not isinstance(item, str):
                    continue

                normalized = " ".join(item.lower().split())

                if normalized and normalized in source:
                    accepted.append(item)

            return accepted

        for field in (
            "education",
            "certifications",
            "responsibilities",
        ):
            extracted = supported_items(
                llm_result.get(field, [])
            )

            if extracted:
                result[field] = extracted

        # Validate experience evidence.
        experience = llm_result.get("experience", {})
        experience_evidence = experience.get("evidence")

        if (
            isinstance(experience_evidence, str)
            and experience_evidence.lower() in source
        ):
            result["minimum_experience"] = (
                experience.get("minimum")
            )
            result["maximum_experience"] = (
                experience.get("maximum")
            )
            result["experience_evidence"] = [
                experience_evidence
            ]

        # Validate job title.
        llm_title = llm_result.get("job_title")

        if (
            isinstance(llm_title, str)
            and llm_title.lower() in source
        ):
            result["job_title"] = llm_title
            result["title"] = llm_title

        # Mark successful LLM analysis.
        result["analysis_provider"] = "groq"

    except Exception as exc:
        logger.exception(
            "TalentIQ Groq JD extraction failed: %s",
            exc,
        )

        result["analysis_provider"] = "python_fallback"
        # Decompose compound requirements into atomic skills.
        result["required_skills"] = decompose_requirements(
            result.get("required_skills", [])
            )

        result["preferred_skills"] = decompose_requirements(
            result.get("preferred_skills", []))

        # Keep metadata synchronized.
        result.setdefault("metadata", {})

        result["metadata"]["mandatory_skill_count"] = len(
            result["required_skills"])

        result["metadata"]["preferred_skill_count"] = len(
            result["preferred_skills"]
            )
        result["metadata"]["total_skills"] = len(
            set(
                result["required_skills"]
                + result["preferred_skills"]))

        result["required_skills"] = decompose_requirements(
            result.get("required_skills", []))

        result["preferred_skills"] = decompose_requirements(
            result.get("preferred_skills", []))

        result.setdefault("metadata", {})
        result["metadata"]["mandatory_skill_count"] = len(result["required_skills"])
        result["metadata"]["preferred_skill_count"] = len(result["preferred_skills"])
        result["metadata"]["total_skills"] = len(set(
             result["required_skills"] + result["preferred_skills"]))
    # IMPORTANT: Return the final result.
    return result
# --------------------------------------------------
# 4. RESUME INTELLIGENCE
# --------------------------------------------------

def extract_resume(text: str) -> dict:
    """Extract structured resume information.

    Preserves the new structured profile while exposing
    legacy top-level fields for the existing dashboard.
    """

    extracted = extract_resume_intelligence(text)

    candidate = extracted.get("candidate", {})
    experience = extracted.get("experience", {})

    professional_years = experience.get(
        "professional_experience_years"
    )

    stated_years = experience.get(
        "stated_experience_years"
    )

    relevant_years = professional_years

    total_years = (
        stated_years
        if stated_years is not None
        else professional_years
    )

    # Legacy compatibility: unknown experience is represented
    # as zero in the old dashboard field.
    if total_years is None:
        total_years = 0

    profile = {
        **extracted,

        "name": candidate.get("name"),
        "email": candidate.get("email"),
        "phone": candidate.get("phone"),

        "total_experience_years": total_years,
        "relevant_experience_years": relevant_years,
        "professional_experience_years": professional_years,

"internship_experience_years": experience.get(
    "internship_experience_years"
),

"stated_experience_years": stated_years,

        "experience_evidence": experience.get(
            "experience_evidence", []
        ),

        "internship_evidence": experience.get(
            "internship_evidence", []
        ),

        "project_evidence": experience.get(
            "project_evidence", []
        ),
    }

    return profile


# --------------------------------------------------
# 5. SEMANTIC SIMILARITY
# --------------------------------------------------

def semantic_similarity(
    requirement: str,
    evidence: str,
) -> float:
    """Calculate semantic similarity between two text strings."""

    if not requirement or not evidence:
        return 0.0

    if not requirement.strip() or not evidence.strip():
        return 0.0

    return calculate_semantic_similarity(
        requirement,
        evidence,
    )


# --------------------------------------------------
# 6. LEGACY SCORING COMPATIBILITY
# --------------------------------------------------

def _score_legacy_candidate(
    jd: dict,
    profile: dict,
    resume_text: str,
) -> dict:
    """Score legacy flat-format candidate profiles."""

    candidate_skills = {
        str(skill).strip().lower()
        for skill in profile.get("skills", [])
        if skill
    }

    required_skills = [
        str(skill).strip().lower()
        for skill in jd.get("required_skills", [])
    ]

    preferred_skills = [
        str(skill).strip().lower()
        for skill in jd.get("preferred_skills", [])
    ]

    matched_required = [
        skill
        for skill in required_skills
        if skill in candidate_skills
    ]

    missing_required = [
        skill
        for skill in required_skills
        if skill not in candidate_skills
    ]

    matched_preferred = [
        skill
        for skill in preferred_skills
        if skill in candidate_skills
    ]

    required_score = (
        len(matched_required) / len(required_skills) * 100
        if required_skills
        else 100
    )

    preferred_score = (
        len(matched_preferred) / len(preferred_skills) * 100
        if preferred_skills
        else 100
    )

    minimum_experience = jd.get("minimum_experience")

    candidate_experience = profile.get(
        "relevant_experience_years"
    )

    if candidate_experience is None:
        candidate_experience = profile.get(
            "total_experience_years"
        )

    if minimum_experience:
        experience_score = min(
            100,
            (candidate_experience or 0)
            / minimum_experience
            * 100,
        )
    else:
        experience_score = 100

    evidence_items = profile.get(
        "experience_evidence", []
    )

    if not evidence_items and resume_text:
        evidence_items = [resume_text]

    semantic_values = []

    for requirement in jd.get("responsibilities", []):
        for evidence in evidence_items:
            semantic_values.append(
                semantic_similarity(
                    str(requirement),
                    str(evidence),
                )
            )

    if semantic_values:
        semantic_score = (
            sum(semantic_values)
            / len(semantic_values)
            * 100
        )
    elif resume_text:
        semantic_score = (
            semantic_similarity(
                " ".join(required_skills),
                resume_text,
            )
            * 100
        )
    else:
        semantic_score = 0

    # Education is neutral when no education requirement
    # has been supplied to this legacy scoring interface.
    education_score = 100

    weights = {
        "skills": 0.35,
        "semantic_relevance": 0.25,
        "experience": 0.20,
        "education": 0.10,
        "preferred_skills": 0.10,
    }

    final_score = (
        required_score * weights["skills"]
        + semantic_score * weights["semantic_relevance"]
        + experience_score * weights["experience"]
        + education_score * weights["education"]
        + preferred_score * weights["preferred_skills"]
    )

    final_score = round(
        max(0, min(100, final_score)),
        2,
    )

    return {
        "score": final_score,

        "breakdown": {
            "skills": round(required_score, 2),
            "semantic_relevance": round(
                semantic_score, 2
            ),
            "experience": round(experience_score, 2),
            "education": round(education_score, 2),
            "preferred_skills": round(
                preferred_score, 2
            ),
        },

        "matched_skills": matched_required,
        "missing_skills": missing_required,
        "partially_matched": [],

        "experience_gap": max(
            0,
            (minimum_experience or 0)
            - (candidate_experience or 0),
        ),

        "evidence": evidence_items,
    }


def _merge_llm_evidence(
    matching_result: dict,
    llm_result: dict,
) -> dict:
    """
    Merge validated LLM evidence into deterministic matching.

    The LLM can improve evidence recognition but cannot
    override stronger deterministic matches.
    """

    if not isinstance(llm_result, dict):
        return matching_result

    evidence_matches = llm_result.get(
        "evidence_matches", []
    )

    if not isinstance(evidence_matches, list):
        return matching_result

    status_priority = {
        "missing": 0,
        "unverified": 1,
        "needs_verification": 2,
        "related_match": 3,
        "exact_match": 4,
    }

    classification_mapping = {
        "explicit_skill": "exact_match",
        "demonstrated_competency": "needs_verification",
        "related_experience": "related_match",
        "unverified": "unverified",
    }

    def normalize(value):
        return " ".join(
            str(value or "").casefold().split()
        )

    llm_by_requirement = {
        normalize(item.get("requirement")): item
        for item in evidence_matches
        if isinstance(item, dict)
    }

    for category in (
        "required_skill_analysis",
        "preferred_skill_analysis",
    ):

        results = matching_result.get(category, [])

        for result in results:

            requirement = normalize(
                result.get("requirement")
            )

            llm_item = llm_by_requirement.get(requirement)

            if not llm_item:
                continue

            classification = llm_item.get(
                "classification"
            )

            new_status = classification_mapping.get(
                classification
            )

            if not new_status:
                continue

            quote = llm_item.get("evidence_quote")

            # The quote must have been validated against
            # the original resume before reaching this helper.
            if new_status != "unverified" and not quote:
                continue

            current_status = result.get(
                "status", "unverified"
            )

            current_priority = status_priority.get(
                current_status, 0
            )

            new_priority = status_priority.get(
                new_status, 0
            )

            # Never downgrade stronger existing evidence.
            if new_priority <= current_priority:
                continue

            result["status"] = new_status

            result["match_type"] = (
                "llm_evidence"
                if new_status != "exact_match"
                else "llm_explicit"
            )

            result["supporting_evidence"] = [quote]

            result["evidence_source"] = (
                llm_item.get("source_section")
            )

            result["llm_confidence"] = (
                llm_item.get("confidence")
            )

            result["explanation"] = (
                llm_item.get("explanation")
                or "Relevant evidence identified by "
                   "the resume evidence analysis."
            )

    matching_result["llm_evidence_analysis"] = (
        evidence_matches
    )

    return matching_result
# --------------------------------------------------
# 7. CANDIDATE SCORING
# --------------------------------------------------

def score_candidate(
    jd: dict,
    profile: dict,
    resume_text: str = "",
) -> dict:
    """Run evidence-aware matching followed by explainable scoring."""

    skills = profile.get("skills", [])

    structured_profile = (
        bool(skills)
        and isinstance(skills[0], dict)
    )

    # Structured profiles use the complete matching pipeline.
    if structured_profile:

        matching_result = match_candidate(
            jd=jd,
            profile=profile,
        )

        # ------------------------------------------
        # LLM RESUME EVIDENCE INTELLIGENCE
        # ------------------------------------------

        try:
            from app.llm_service import analyze_resume_evidence

            required_skills = jd.get(
                "required_skills", []
            ) or []

            preferred_skills = jd.get(
                "preferred_skills", []
            ) or []

            if resume_text and resume_text.strip():

                llm_result = analyze_resume_evidence(
                    resume_text=resume_text,
                    required_skills=required_skills,
                    preferred_skills=preferred_skills,
                )

                matching_result = _merge_llm_evidence(
                    matching_result,
                    llm_result,
                )

        except Exception:
            logger.exception(
                "TalentIQ resume evidence analysis failed. "
                "Using deterministic matching results."
            )

        # ------------------------------------------
        # EXISTING DETERMINISTIC SCORING
        # ------------------------------------------

        scoring_result = calculate_candidate_score(
            jd=jd,
            profile=profile,
            matching_result=matching_result,
        )

        scoring_result["matching_result"] = (
            matching_result
        )

        return scoring_result

    # Legacy flat profiles retain compatibility.
    return _score_legacy_candidate(
        jd=jd,
        profile=profile,
        resume_text=resume_text,
    )


# --------------------------------------------------
# 8. CANDIDATE EXPLANATIONS
# --------------------------------------------------

def explain(
    result: dict,
    profile: dict,
) -> dict:
    """
    Create a dashboard-friendly, evidence-based candidate explanation.

    Exposes provisional scores, evidence coverage, unevaluated
    components and human-review warnings.
    """

    candidate_name = (
        profile.get("name")
        or profile.get("candidate", {}).get("name")
        or "Candidate"
    )

    score = result.get("score")
    score_status = result.get("score_status", "unknown")

    provisional_score = result.get("provisional_score")
    if provisional_score is None:
        provisional_score = score

    evidence_coverage = result.get(
        "evidence_coverage",
        result.get("evaluated_weight", 0)
    )

    unevaluated_weight = result.get(
        "unevaluated_weight",
        0
    )

    evidence_adjusted_score = result.get(
        "evidence_adjusted_score"
    )

    if score_status == "complete" and score is not None:
        score_text = f"{score:.2f}%"
    elif score_status == "partial" and provisional_score is not None:
        score_text = f"{provisional_score:.2f}% (Provisional)"

    else:
        score_text = "Insufficient evidence"


    required_analysis = result.get(
        "required_skill_analysis",
        []
    )

    preferred_analysis = result.get(
        "preferred_skill_analysis",
        []
    )

    satisfied = [
        item.get("requirement")
        for item in required_analysis
        if item.get("status") == "exact_match"
    ]

    related = [
        item.get("requirement")
        for item in required_analysis
        if item.get("status") == "related_match"
    ]

    not_verified = [
    item.get("requirement")
    for item in required_analysis
    if item.get("status") in (
        "unverified",
        "needs_verification",
    )
]

    missing = [
        item.get("requirement")
        for item in required_analysis
        if item.get("status") == "missing"
    ]

    needs_verification = result.get(
        "skills_needing_verification",
        []
    )

    verify_in_interview = list(dict.fromkeys(
        related + needs_verification
    ))

    # Preserve component scores and their evaluation status.
    score_breakdown = {}

    for component, details in result.get(
        "breakdown", {}
    ).items():

        if isinstance(details, dict):
            score_breakdown[component] = {
                "score": details.get("score"),
                "verified_score": details.get(
                    "verified_score"
                ),
                "weight": details.get("weight"),
                "contribution": details.get(
                    "contribution"
                ),
                "status": details.get(
                    "status",
                    "not_evaluated"
                ),
            }

        else:
            score_breakdown[component] = {
                "score": details,
                "status": "evaluated",
            }

    experience = result.get(
        "experience_analysis",
        {}
    )

    education = result.get(
        "education_analysis",
        {}
    )

    semantic = result.get(
        "semantic_analysis",
        {}
    )

    # Generate an honest summary.
    if score_status == "complete":
        summary = (
            f"{candidate_name} received a match score of "
            f"{score_text}. All scoring components were evaluated."
        )

    elif score_status == "partial":
        summary = (
            f"{candidate_name} received a provisional match score "
            f"of {score_text}. Only {evidence_coverage:.2f}% "
            f"of the scoring weight was evaluated. "
            f"The remaining {unevaluated_weight:.2f}% "
            f"requires additional evidence or review."
        )

    else:
        summary = (
            f"A reliable match score could not be calculated "
            f"for {candidate_name} because sufficient evidence "
            f"was unavailable."
        )

    return {
        "candidate_name": candidate_name,

        "summary": summary,

        # Overall scoring
        "score": score,
        "provisional_score": provisional_score,
        "evidence_adjusted_score": evidence_adjusted_score,
        "score_status": score_status,

        # Evidence coverage
        "evidence_coverage": evidence_coverage,
        "evaluated_weight": evidence_coverage,
        "unevaluated_weight": unevaluated_weight,

        # Skills
        "satisfied": satisfied,
        "related_skills": related,
        "not_verified": not_verified,
        "missing_skills": missing,
        "verify_in_interview": verify_in_interview,

        # Detailed scoring
        "score_breakdown": score_breakdown,
        "component_analysis": result.get(
            "component_analysis",
            {}
        ),

        "required_skill_analysis": required_analysis,
        "preferred_skill_analysis": preferred_analysis,

        # Other evaluation dimensions
        "experience_analysis": experience,
        "education_analysis": education,
        "semantic_analysis": semantic,

        # Explanations and warnings
        "scoring_explanations": result.get(
            "explanations",
            []
        ),

        "ranking_warning": result.get(
            "ranking_warning"
        ),

        "scoring_method": result.get(
            "method",
            "legacy_scoring"
        ),

        "scoring_weights": result.get(
            "scoring_weights",
            {}
        ),
    }


# --------------------------------------------------
# 9. CANDIDATE RANKING
# --------------------------------------------------

def rank_candidates(rows: list[dict]) -> list[dict]:
    """Rank dashboard candidate records using Ranking Engine."""

    if not rows:
        return []

    
    return engine_rank_candidates(rows)