import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()


# ==================================================
# 1. JOB DESCRIPTION MODELS
# ==================================================

class ExperienceRequirement(BaseModel):
    minimum: float | None = None
    maximum: float | None = None
    evidence: str | None = None


class JDExtraction(BaseModel):
    job_title: str | None = None

    required_skills: list[str] = Field(
        default_factory=list
    )

    preferred_skills: list[str] = Field(
        default_factory=list
    )

    unclassified_skills: list[str] = Field(
        default_factory=list
    )

    experience: ExperienceRequirement

    education: list[str] = Field(
        default_factory=list
    )

    certifications: list[str] = Field(
        default_factory=list
    )

    responsibilities: list[str] = Field(
        default_factory=list
    )

    domain: str | None = None
    seniority: str | None = None
    employment_type: str | None = None


# ==================================================
# 2. RESUME EVIDENCE MODELS
# ==================================================

class RequirementEvidence(BaseModel):

    requirement: str

    classification: Literal[
        "explicit_skill",
        "demonstrated_competency",
        "related_experience",
        "unverified"
    ]

    evidence_quote: str | None = None

    source_section: str | None = None

    confidence: float = Field(
        ge=0,
        le=1
    )

    explanation: str


class ResumeEvidenceAnalysis(BaseModel):

    evidence_matches: list[RequirementEvidence] = Field(
        default_factory=list
    )


# ==================================================
# 3. LLM INITIALIZATION
# ==================================================

@lru_cache(maxsize=1)
def get_llm():

    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL")

    if not api_key or not model:
        raise RuntimeError(
            "Groq configuration is missing."
        )

    return ChatGroq(
        model=model,
        temperature=0,
        max_retries=2,
        timeout=45,
    )


# ==================================================
# 4. JOB DESCRIPTION EXTRACTION
# ==================================================

def extract_jd_with_llm(description: str) -> dict:

    llm = get_llm()

    structured_llm = llm.with_structured_output(
        JDExtraction,
        method="json_schema",
        strict=True,
    )

    prompt = ChatPromptTemplate.from_messages([

        (
            "system",
            """
            You are TalentIQ's Job Description Intelligence Engine.

            Extract only information explicitly supported by the
            supplied job description.

            Rules:

            1. Never invent skills or qualifications.
            2. Separate mandatory and preferred skills.
            3. Preserve the original evidence for experience.
            4. Distinguish education from responsibilities.
            5. Extract only genuine certifications.
            6. Do not treat academic projects as work experience.
            7. If information is absent, return an empty list or null.
            8. Do not interpret years of experience as a candidate's age.
            """
        ),

        ("human", "{description}"),

    ])

    chain = prompt | structured_llm

    result = chain.invoke({
        "description": description
    })

    return result.model_dump()


# ==================================================
# 5. RESUME EVIDENCE INTELLIGENCE
# ==================================================

def analyze_resume_evidence(
    resume_text: str,
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> dict:

    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError(
            "Resume text cannot be empty."
        )

    required_skills = required_skills or []
    preferred_skills = preferred_skills or []

    llm = get_llm()

    structured_llm = llm.with_structured_output(
        ResumeEvidenceAnalysis,
        method="json_schema",
        strict=True,
    )

    prompt = ChatPromptTemplate.from_messages([

        (
            "system",
            """
            You are TalentIQ's Resume Evidence Intelligence Engine.

            Your task is to evaluate whether a candidate's resume
            contains evidence supporting specific job requirements.

            EVIDENCE CLASSIFICATIONS:

            1. explicit_skill:
               The candidate directly lists the required skill
               in the resume.

            2. demonstrated_competency:
               The candidate describes actual work or project
               activities that demonstrate the required capability.

            3. related_experience:
               The candidate has relevant but indirect or
               transferable experience.

            4. unverified:
               Sufficient supporting evidence cannot be found.

            IMPORTANT RULES:

            1. Evaluate every supplied requirement separately.

            2. Every evidence_quote must be copied verbatim
               from the supplied resume.

            3. Never invent responsibilities, skills,
               achievements, qualifications or experience.

            4. Do not assume that using a tool proves expertise
               in every capability associated with that tool.

            5. Distinguish professional experience, internships,
               projects and education.

            6. Do not confuse semantic similarity with proof
               of competency.

            7. Confidence represents your assessment of evidence
               relevance, not the truthfulness of candidate claims.

            8. If evidence is unavailable, return null for
               evidence_quote and source_section.

            9. Do not classify a related skill as an explicit skill.

            10. Do not classify an academic project as
                professional work experience.

            11. Include the original resume section as source_section
                when it can be identified.

            12. Return one assessment for every supplied requirement.
            """
        ),

        (
            "human",
            """
            RESUME:

            {resume_text}

            REQUIRED SKILLS:

            {required_skills}

            PREFERRED SKILLS:

            {preferred_skills}

            Analyse the evidence for every requirement.
            """
        ),

    ])

    chain = prompt | structured_llm

    result = chain.invoke({

        "resume_text": resume_text,

        "required_skills": required_skills,

        "preferred_skills": preferred_skills,

    })

    # ==================================================
    # 6. EVIDENCE VALIDATION
    # ==================================================

    normalized_resume = " ".join(
        resume_text.lower().split()
    )

    validated_matches = []

    for match in result.evidence_matches:

        item = match.model_dump()

        quote = item.get("evidence_quote")

        if quote:

            normalized_quote = " ".join(
                quote.lower().split()
            )

            # Verify that the evidence actually exists
            # in the original resume.

            if normalized_quote not in normalized_resume:

                item["classification"] = "unverified"

                item["evidence_quote"] = None

                item["source_section"] = None

                item["confidence"] = 0.0

                item["explanation"] = (
                    "The proposed evidence could not be "
                    "verified against the original resume text."
                )

        validated_matches.append(item)

    return {
        "evidence_matches": validated_matches
    }
