from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy import select

import hashlib
import json
import csv
import io
import re

from .database import init_db, SessionLocal, Job, Candidate
from .core import MAX_FILE_BYTES, UPLOAD_DIR
from .services import (
    analyze_jd,
    parse_document,
    extract_resume,
    score_candidate,
    explain,
    rank_candidates,
)
from .candidate_intelligence import (
    compare_candidates,
    explain_ranking,
    evaluate_ranking,
)


# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

app = FastAPI(
    title="TalentIQ — AI Recruitment Intelligence",
    version="0.1.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

if not FRONTEND_DIR.is_dir():
    raise RuntimeError(
        f"Frontend directory not found: {FRONTEND_DIR}"
    )


# =========================================================
# FRONTEND STATIC FILES
# =========================================================

app.mount(
    "/frontend",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="frontend",
)


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

init_db()


# =========================================================
# REQUEST MODELS
# =========================================================

class JobIn(BaseModel):
    title: str | None = None
    description: str = Field(min_length=1)


class CompareIn(BaseModel):
    candidate_ids: list[int] = Field(min_length=2)


class EvaluateRankingIn(BaseModel):
    relevant_candidate_ids: list[int] = Field(
        default_factory=list
    )
    k: int | None = Field(default=None, ge=1)


class RequirementsIn(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)


# =========================================================
# FRONTEND HOME PAGE
# =========================================================

@app.get("/")
def home():
    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():
    return {"status": "ok"}


# =========================================================
# JOB MANAGEMENT
# =========================================================

@app.post("/api/jobs")
def create_job(body: JobIn):

    # Normalize description to detect repeated submissions.
    normalized_description = " ".join(
        body.description.casefold().split()
    )

    with SessionLocal() as db:

        # Check whether this exact JD already exists.
        existing_jobs = db.scalars(
            select(Job)
        ).all()

        for existing in existing_jobs:
            existing_description = " ".join(
                (existing.description or "").casefold().split()
            )

            if existing_description == normalized_description:
                return {
                    "id": existing.id,
                    "title": existing.title,
                    "requirements": json.loads(
                        existing.requirements_json
                    ),
                    "existing": True,
                }

        # Create a new JD only when no duplicate exists.
        requirements = analyze_jd(body.description)

        job = Job(
            title=body.title or requirements["title"],
            description=body.description,
            requirements_json=json.dumps(requirements),
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        return {
            "id": job.id,
            "title": job.title,
            "requirements": requirements,
            "existing": False,
        }


@app.get("/api/jobs")
def list_jobs():

    with SessionLocal() as db:

        jobs = db.scalars(
            select(Job)
        ).all()

        return [
            {
                "id": job.id,
                "title": job.title,
                "requirements": json.loads(
                    job.requirements_json
                ),
            }
            for job in jobs
        ]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: int):

    with SessionLocal() as db:

        job = db.get(Job, job_id)

        if not job:
            raise HTTPException(
                404,
                "Job not found"
            )

        return {
            "id": job.id,
            "title": job.title,
            "description": job.description,
            "requirements": json.loads(
                job.requirements_json
            ),
        }


# =========================================================
# UPDATE JOB REQUIREMENTS
# =========================================================

@app.patch("/api/jobs/{job_id}/requirements")
def update_requirements(
    job_id: int,
    body: RequirementsIn,
):

    with SessionLocal() as db:

        job = db.get(Job, job_id)

        if not job:
            raise HTTPException(
                404,
                "Job not found"
            )

        requirements = json.loads(
            job.requirements_json
        )

        requirements["required_skills"] = list(
            dict.fromkeys(
                skill.strip().lower()
                for skill in body.required_skills
                if skill.strip()
            )
        )

        requirements["preferred_skills"] = [
            skill
            for skill in dict.fromkeys(
                item.strip().lower()
                for item in body.preferred_skills
                if item.strip()
            )
            if skill not in requirements["required_skills"]
        ]

        job.requirements_json = json.dumps(
            requirements
        )

        candidates = db.scalars(
            select(Candidate).where(
                Candidate.job_id == job_id
            )
        ).all()

        for candidate in candidates:

            profile = json.loads(
                candidate.profile_json
            )

            result = score_candidate(
                requirements,
                profile,
                candidate.text,
            )

            candidate.score = result["score"]

            candidate.explanation_json = json.dumps(
                explain(result, profile)
            )

        db.commit()

        return {
            "requirements": requirements,
            "updated": True,
        }


# =========================================================
# RESUME UPLOAD
# =========================================================

@app.post("/api/resumes/upload")
async def upload(
    request: Request,
    job_id: int,
):

    content_type = request.headers.get(
        "content-type",
        ""
    )

    match = re.search(
        r'boundary=(?:"([^"]+)"|([^;]+))',
        content_type,
    )

    if not match:
        raise HTTPException(
            400,
            "Expected multipart form data"
        )

    boundary = (
        match.group(1) or match.group(2)
    ).encode()

    body = await request.body()

    files = []

    for part in body.split(b"--" + boundary):

        if b"content-disposition" not in part.lower():
            continue

        header, separator, data = part.partition(
            b"\r\n\r\n"
        )

        if not separator:
            continue

        disposition = header.decode(
            "utf-8",
            errors="replace",
        )

        filename_match = re.search(
            r'filename="([^"]*)"',
            disposition,
        )

        if filename_match:

            files.append(
                (
                    filename_match.group(1),
                    data.removesuffix(
                        b"\r\n"
                    ).removesuffix(b"--"),
                )
            )

    if not files:
        raise HTTPException(
            400,
            "No files found in upload"
        )

    results = []

    with SessionLocal() as db:

        if not db.get(Job, job_id):
            raise HTTPException(
                404,
                "Job not found"
            )

        for filename, raw in files:

            try:

                name = (
                    filename or "resume"
                ).replace("\\", "/").split("/")[-1]

                if len(raw) > MAX_FILE_BYTES:
                    raise ValueError(
                        "File exceeds 8 MB size limit"
                    )

                digest = hashlib.sha256(
                    raw
                ).hexdigest()

                duplicate = db.scalar(
                    select(Candidate).where(
                        Candidate.job_id == job_id,
                        Candidate.digest == digest,
                    )
                )

                if duplicate:

                    results.append({
                        "filename": name,
                        "status": "duplicate",
                        "candidate_id": duplicate.id,
                    })

                    continue

                text = parse_document(
                    name,
                    raw,
                )

                if not text.strip():
                    raise ValueError(
                        "Document has no extractable text"
                    )

                profile = extract_resume(text)

                job = db.get(Job, job_id)

                result = score_candidate(
                    json.loads(job.requirements_json),
                    profile,
                    text,
                )

                candidate = Candidate(
                    job_id=job_id,
                    filename=name,
                    digest=digest,
                    text=text,
                    profile_json=json.dumps(profile),
                    score=result["score"],
                    explanation_json=json.dumps(
                        explain(result, profile)
                    ),
                )

                db.add(candidate)
                db.flush()

                UPLOAD_DIR.joinpath(
                    f"{candidate.id}.bin"
                ).write_bytes(raw)

                results.append({
                    "filename": name,
                    "status": "processed",
                    "candidate_id": candidate.id,
                    "score": candidate.score,
                    "name": profile["name"],
                })

            except Exception as error:

                results.append({
                    "filename": filename,
                    "status": "failed",
                    "error": str(error),
                })

        db.commit()

    return {
        "results": results,
        "processed": sum(
            item["status"] == "processed"
            for item in results
        ),
    }


# =========================================================
# CANDIDATE SERIALIZATION
# =========================================================

def serialize(candidate):
    profile = json.loads(candidate.profile_json)
    explanation = json.loads(candidate.explanation_json)

    return {
        "id": candidate.id,
        "job_id": candidate.job_id,
        "filename": candidate.filename,
        "name": profile.get("name") or "Unknown candidate",
        "email": profile.get("email"),
        "phone": profile.get("phone"),
        "status": candidate.status,

        # Overall score
        "score": candidate.score,
        "provisional_score": explanation.get(
            "provisional_score",
            candidate.score
        ),

        # Evidence quality
        "score_status": explanation.get(
            "score_status",
            "unknown"
        ),
        "evidence_coverage": explanation.get(
            "evidence_coverage",
            explanation.get("evaluated_weight", 0)
        ),
        "unevaluated_weight": explanation.get(
            "unevaluated_weight",
            0
        ),

        "ranking_warning": explanation.get(
            "ranking_warning"
        ),

        # Full candidate information
        "profile": profile,
        "explanation": explanation,
    }


# =========================================================
# MATCHING RESULTS
# =========================================================

@app.get("/api/matching/results/{job_id}")
def results(job_id: int):

    with SessionLocal() as db:

        if not db.get(Job, job_id):
            raise HTTPException(
                404,
                "Job not found"
            )

        candidates = db.scalars(
            select(Candidate).where(
                Candidate.job_id == job_id
            )
        ).all()

        rows = [
            serialize(candidate)
            for candidate in candidates
        ]

        # Use the central Ranking Engine for consistent ranking.
        # Unscored candidates remain unscored and are placed last.
        rows = rank_candidates(rows)

        rank_position = 0
        for rank, row in enumerate(rows, start=1):
            if row.get("provisional_score") is None:
                row["rank"] = None
                row["ranking_status"] = "unscored"
            else:
                rank_position += 1
                row["rank"] = rank_position
                row["ranking_status"] = "ranked"

            row["matched_count"] = len(
                row["explanation"].get("satisfied", [])
            )

            row["ranking_basis"] = (
                "Provisional score; evidence coverage used "
                "as a tie-breaker."
            )

        return rows

# =========================================================
# RESUME DETAILS
# =========================================================

@app.get("/api/resumes/{resume_id}")
def resume(resume_id: int):

    with SessionLocal() as db:

        candidate = db.get(
            Candidate,
            resume_id,
        )

        if not candidate:
            raise HTTPException(
                404,
                "Candidate not found"
            )

        return serialize(candidate)


@app.get("/api/candidates/{candidate_id}")
def candidate(candidate_id: int):

    return resume(candidate_id)


@app.get("/api/candidates/{candidate_id}/explanation")
def candidate_explanation(candidate_id: int):

    return resume(candidate_id)["explanation"]


# =========================================================
# DELETE CANDIDATE
# =========================================================

@app.delete("/api/resumes/{resume_id}")
def delete_resume(resume_id: int):

    with SessionLocal() as db:

        candidate = db.get(
            Candidate,
            resume_id,
        )

        if not candidate:
            raise HTTPException(
                404,
                "Candidate not found"
            )

        UPLOAD_DIR.joinpath(
            f"{candidate.id}.bin"
        ).unlink(missing_ok=True)

        db.delete(candidate)
        db.commit()

        return {
            "deleted": resume_id
        }


# =========================================================
# CANDIDATE COMPARISON
# =========================================================

@app.post("/api/candidates/compare")
def compare(body: CompareIn):

    requested_ids = list(
        dict.fromkeys(body.candidate_ids)
    )

    if len(requested_ids) < 2:
        raise HTTPException(
            422,
            "Select at least two different candidates"
        )

    with SessionLocal() as db:

        records = db.scalars(
            select(Candidate).where(
                Candidate.id.in_(requested_ids)
            )
        ).all()

        if len(records) != len(requested_ids):
            raise HTTPException(
                404,
                "One or more candidates not found"
            )

        by_id = {
            record.id: record
            for record in records
        }

        ordered_records = [
            by_id[candidate_id]
            for candidate_id in requested_ids
        ]

        job_ids = {
            record.job_id
            for record in ordered_records
        }

        if len(job_ids) != 1:
            raise HTTPException(
                400,
                "Candidates must belong to the same job to be compared",
            )

        rows = [
            serialize(record)
            for record in ordered_records
        ]

        return compare_candidates(
            rows,
        )


# =========================================================
# RANKING EXPLANATION
# =========================================================

@app.get("/api/jobs/{job_id}/ranking/explanation")
def get_ranking_explanation(job_id: int):

    with SessionLocal() as db:

        if not db.get(Job, job_id):
            raise HTTPException(
                404,
                "Job not found"
            )

        rows = [
            serialize(candidate)
            for candidate in db.scalars(
                select(Candidate).where(
                    Candidate.job_id == job_id
                )
            ).all()
        ]

        ranked_rows = rank_candidates(rows)

        explanations = explain_ranking(
            ranked_rows
        )

        return {
            "job_id": job_id,
            "candidate_count": len(ranked_rows),
            "ranking_explanations": explanations,
            "note": (
                "These explanations describe observed score differences "
                "and available resume evidence; they do not establish "
                "candidate quality or predict job performance."
            ),
        }


# =========================================================
# RANKING EVALUATION
# =========================================================

@app.post("/api/jobs/{job_id}/ranking/evaluation")
def evaluate_job_ranking(
    job_id: int,
    body: EvaluateRankingIn,
):

    with SessionLocal() as db:

        if not db.get(Job, job_id):
            raise HTTPException(
                404,
                "Job not found"
            )

        rows = [
            serialize(candidate)
            for candidate in db.scalars(
                select(Candidate).where(
                    Candidate.job_id == job_id
                )
            ).all()
        ]

        ranked_rows = rank_candidates(rows)

        ranked_ids = [
            candidate["id"]
            for candidate in ranked_rows
        ]

        relevant_ids = set(
            body.relevant_candidate_ids
        )

        unknown_ids = (
            relevant_ids - set(ranked_ids)
        )

        if unknown_ids:
            raise HTTPException(
                400,
                {
                    "message": (
                        "Some labelled candidates do not belong to this job."
                    ),
                    "unknown_candidate_ids": sorted(
                        unknown_ids
                    ),
                },
            )

        metrics = evaluate_ranking(
            ranked_candidate_ids=ranked_ids,
            relevant_candidate_ids=relevant_ids,
            k=body.k,
        )

        return {
            "job_id": job_id,
            "metrics": metrics,
            "note": (
                "Metrics use independently supplied relevance labels. "
                "Do not derive those labels from TalentIQ's own scores."
            ),
        }

# =========================================================
# RECALCULATE EXISTING CANDIDATES
# =========================================================

@app.post("/api/jobs/{job_id}/recalculate")
def recalculate_candidates(job_id: int):

    with SessionLocal() as db:

        # Verify that the job exists.
        job = db.get(Job, job_id)

        if not job:
            raise HTTPException(
                status_code=404,
                detail="Job not found"
            )

        requirements = json.loads(
            job.requirements_json
        )

        # Retrieve all existing candidates.
        candidates = db.scalars(
            select(Candidate).where(
                Candidate.job_id == job_id
            )
        ).all()

        recalculated = []
        failed = []

        # Calculate first, then update database records.
        # This avoids partially updating candidates if
        # an unexpected error occurs.
        for candidate in candidates:

            try:
                profile = json.loads(
                    candidate.profile_json
                )

                result = score_candidate(
                    requirements,
                    profile,
                    candidate.text
                )

                explanation = explain(
                    result,
                    profile
                )

                recalculated.append({
                    "candidate": candidate,
                    "score": result.get("score"),
                    "explanation": explanation,
                })

            except Exception as error:

                failed.append({
                    "candidate_id": candidate.id,
                    "filename": candidate.filename,
                    "error": str(error),
                })

        # Save successfully recalculated candidates.
        for item in recalculated:

            candidate = item["candidate"]

            candidate.score = item["score"]

            candidate.explanation_json = json.dumps(
                item["explanation"]
            )

        db.commit()

        # Summarize the new evaluation statuses.
        status_counts = {
            "complete": 0,
            "partial": 0,
            "insufficient_evidence": 0,
            "unknown": 0,
        }

        for item in recalculated:

            status = item["explanation"].get(
                "score_status",
                "unknown"
            )

            if status not in status_counts:
                status = "unknown"

            status_counts[status] += 1

        return {
            "success": True,
            "job_id": job_id,
            "total_candidates": len(candidates),
            "recalculated": len(recalculated),
            "failed": len(failed),
            "evaluation_summary": status_counts,
            "failures": failed,
            "message": (
                "Candidate scores and explanations "
                "have been recalculated."
            ),
        }


# =========================================================
# CSV EXPORT
# =========================================================

@app.get("/api/candidates/export/{job_id}")
def export(job_id: int):
    rows = results(job_id)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Rank",
        "Candidate Name",
        "Filename",
        "Match Score (%)",
        "Score Status",
        "Evidence Coverage (%)",
        "Unevaluated Weight (%)",
        "Scoring Component Weights",
        "Matched Required Skills",
        "Unverified Required Skills",
        "Missing Required Skills",
        "Experience Years",
        "Ranking Warning",
        "Processing Status",
    ])

    for rank, row in enumerate(rows, start=1):
        explanation = row.get("explanation") or {}
        profile = row.get("profile") or {}

        # Complete evaluations use score.
        # Partial evaluations use provisional_score.
        match_score = row.get("score")

        if match_score is None:
            match_score = row.get("provisional_score")

        if match_score is None:
            match_score = explanation.get("provisional_score")

        # Export actual scoring component weights.
        breakdown = explanation.get("score_breakdown") or {}

        component_weights = ", ".join(
            f"{name}: {details['weight']}%"
            for name, details in breakdown.items()
            if isinstance(details, dict)
            and details.get("weight") is not None
        )

        writer.writerow([
            rank,
            row.get("name"),
            row.get("filename"),
            match_score,
            row.get("score_status") or explanation.get("score_status"),
            row.get("evidence_coverage", explanation.get("evidence_coverage")),
            row.get("unevaluated_weight", explanation.get("unevaluated_weight")),
            component_weights,
            ", ".join(explanation.get("satisfied") or []),
            ", ".join(explanation.get("not_verified") or []),
            ", ".join(explanation.get("missing_skills") or []),
            profile.get("total_experience_years"),
            row.get("ranking_warning") or "",
            row.get("status"),
        ])

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=talentiq-job-{job_id}.csv"
            )
        },
    )