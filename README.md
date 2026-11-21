# TalentIQ — AI-Powered Resume Matching & Candidate Intelligence

TalentIQ is an AI-assisted recruitment platform that evaluates candidate resumes against job descriptions using semantic relevance, skill matching, experience analysis and evidence-based scoring.

Instead of relying exclusively on keyword matching, TalentIQ provides recruiters with explainable candidate evaluations, supporting evidence and comparative insights.

## Key Features

- **Job Description Analysis:** Extract structured hiring requirements, required skills and preferred skills.
- **Batch Resume Upload:** Upload multiple PDF and DOCX resumes.
- **Resume Parsing:** Extract candidate profiles, skills, education, experience and project information.
- **AI-Powered Matching:** Evaluate candidates against specific job requirements.
- **Candidate Ranking:** Rank candidates using weighted matching scores.
- **Candidate Intelligence:** Explore detailed candidate profiles and supporting resume evidence.
- **Explainable Scoring:** Understand why candidates receive particular scores.
- **Candidate Comparison:** Compare multiple candidates across relevant evaluation criteria.
- **Recruiter Analytics:** View candidate distributions, evidence coverage and skill coverage.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Styling | CSS |
| Icons | Lucide React |
| Backend | Python, FastAPI |
| Database | SQLite |
| AI Integration | Groq API, LangChain |
| API Architecture | REST |

## System Architecture

```text
                 RECRUITER
                     |
                     v
          React + TypeScript Frontend
                (frontend-react)
                     |
                     v
              FastAPI Backend
                    (app)
                     |
          +----------+----------+
          |          |          |
          v          v          v
       JD Parser  Resume     Evaluation
                  Parser       Engine
          |          |          |
          +----------+----------+
                     |
                     v
               SQLite Database
```

## Candidate Scoring Methodology

TalentIQ uses a weighted evaluation model with five components.

| Evaluation Component | Weight |
|---|---:|
| Required Skills | 35% |
| Semantic Relevance | 25% |
| Relevant Experience | 20% |
| Education & Qualifications | 10% |
| Preferred Skills | 10% |
| **Total** | **100%** |

### Evidence-Based Skill Evaluation

Skills are evaluated using the following evidence classifications:

| Classification | Value |
|---|---:|
| Exact Match | 1.00 |
| Related Match | 0.50 |
| Needs Verification | 0.25 |

The evaluation engine also considers evidence coverage and provides requirement-level explanations.

Insufficient information is not automatically treated as proof that a candidate lacks a qualification.

### Explainability

Each candidate evaluation can include:

- Overall matching score.
- Component-level score breakdown.
- Matched and related skills.
- Missing and unverified requirements.
- Experience and education analysis.
- Supporting resume evidence.
- Ranking explanations.

Scores are decision-support signals and should be reviewed alongside the underlying evidence.

## Installation and Setup

### Prerequisites

- Python 3.10+
- Node.js and npm
- Git
- Groq API credentials, if required by the configured JD extraction workflow.

### 1. Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <PROJECT_DIRECTORY>
```

### 2. Backend Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Configure the required environment variables in a local `.env` file. Never commit API keys or secrets.

Start the backend:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend API documentation:

`http://127.0.0.1:8000/docs`

### 3. Frontend Setup

Open another terminal:

```bash
cd frontend-react
npm install
npm run dev
```

Open the local URL displayed by Vite.

### 4. Run Backend Tests

From the project root:

```bash
python -m pytest -q
```

## API Overview

| Functionality | Endpoint |
|---|---|
| List Jobs | GET `/api/jobs` |
| Create Job | POST `/api/jobs` |
| Get Job Details | GET `/api/jobs/{job_id}` |
| Update Requirements | PATCH `/api/jobs/{job_id}/requirements` |
| Candidate Results | GET `/api/matching/results/{job_id}` |
| Upload Resumes | POST `/api/resumes/upload` |
| Delete Candidate | DELETE `/api/resumes/{candidate_id}` |
| Compare Candidates | POST `/api/candidates/compare` |
| Ranking Explanation | GET `/api/jobs/{job_id}/ranking/explanation` |
| Ranking Evaluation | POST `/api/jobs/{job_id}/ranking/evaluation` |
| Recalculate Ranking | POST `/api/jobs/{job_id}/recalculate` |
| Export Candidates | GET `/api/candidates/export/{job_id}` |

Refer to the running FastAPI documentation for the exact request and response schemas.

## Testing Strategy

TalentIQ should be evaluated using synthetic or appropriately licensed resumes.

Recommended test scenarios:

1. Upload at least 10 PDF/DOCX resumes in one batch.
2. Compare strong, moderate and weak candidate profiles.
3. Test exact and semantically related skill descriptions.
4. Evaluate internship, project-based and professional experience.
5. Test incomplete and ambiguous resume evidence.
6. Evaluate different job domains, including AI/ML, operations, HR and digital marketing.

## Responsible Use

TalentIQ is designed to assist recruiters, not replace human decision-making.

- Use authorized candidate information.
- Protect uploaded resumes and personal information.
- Store API credentials securely.
- Review supporting evidence before making hiring decisions.
- Do not interpret a matching score as a guarantee of job performance.

## Deployment

The application requires separate frontend and backend deployments.

The frontend must communicate with the deployed FastAPI backend rather than the local development server.

The backend requires production environment variables, appropriate CORS configuration and persistent storage.

The current local configuration uses SQLite. Before public deployment, configure persistent database storage or migrate to a managed database. Uploaded resumes also require persistent storage.

## Project Status

TalentIQ is a working prototype developed as an AI-based resume matching and candidate ranking system.

## License

Add the appropriate license before public distribution.