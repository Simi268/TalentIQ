import math

from app.quality_assurance import (
    assess_extracted_text,
    assess_resume_profile,
    validate_score_result,
    validate_upload,
)


def test_upload_rejects_empty_file():
    result = validate_upload("resume.pdf", b"")
    assert result["valid"] is False
    assert "The uploaded file is empty." in result["errors"]


def test_upload_rejects_unsupported_extension():
    result = validate_upload("resume.exe", b"not really a file")
    assert result["valid"] is False
    assert any("Only PDF" in error for error in result["errors"])


def test_upload_rejects_file_over_limit():
    result = validate_upload("resume.txt", b"x" * 20, max_file_bytes=10)
    assert result["valid"] is False
    assert any("upload limit" in error for error in result["errors"])


def test_upload_checks_pdf_signature_and_hash():
    result = validate_upload("resume.pdf", b"not a pdf")
    assert result["valid"] is False
    assert result["sha256"] is not None


def test_upload_accepts_small_text_file():
    result = validate_upload("resume.txt", b"Python developer")
    assert result["valid"] is True
    assert result["extension"] == ".txt"


def test_extracted_text_flags_empty_document():
    result = assess_extracted_text("")
    assert result["ok"] is False
    assert result["word_count"] == 0


def test_extracted_text_warns_on_very_short_document():
    result = assess_extracted_text("Python developer")
    assert result["ok"] is True
    assert result["warnings"]


def test_profile_does_not_require_contact_details():
    profile = {
        "name": "Example Candidate",
        "skills": ["python"],
        "experience_evidence": ["Built an API"],
        "project_evidence": ["Resume parser"],
        "education": "BTech",
        "email": None,
        "phone": None,
        "relevant_experience_years": 1,
    }
    result = assess_resume_profile(profile, "A sufficiently long extracted resume text " * 8)
    assert result["contact"] == {
        "email_present": False,
        "phone_present": False,
    }
    assert result["quality_status"] == "ok"


def test_profile_flags_missing_evidence_without_inventing_it():
    result = assess_resume_profile(
        {"skills": [], "experience_evidence": [], "projects": []}
    )
    assert result["quality_status"] == "needs_review"
    assert len(result["review_items"]) >= 3


def test_profile_warns_on_implausible_experience():
    result = assess_resume_profile(
        {"skills": ["python"], "relevant_experience_years": 99}
    )
    assert any("exceeds 50 years" in warning for warning in result["warnings"])


def test_score_result_accepts_valid_payload():
    result = validate_score_result({
        "score": 82.5,
        "breakdown": {
            "skills": 90,
            "experience": 75,
        },
        "weights": {
            "skills": 0.5,
            "experience": 0.5,
        },
    })
    assert result["valid"] is True
    assert result["errors"] == []


def test_score_result_rejects_out_of_range_score():
    result = validate_score_result({
        "score": 101,
        "breakdown": {"skills": 90},
    })
    assert result["valid"] is False
    assert any("between 0 and 100" in error for error in result["errors"])


def test_score_result_rejects_nan():
    result = validate_score_result({
        "score": math.nan,
        "breakdown": {"skills": 50},
    })
    assert result["valid"] is False


def test_score_result_warns_if_weights_do_not_sum_to_one():
    result = validate_score_result({
        "score": 70,
        "breakdown": {"skills": 70},
        "weights": {"skills": 0.3, "experience": 0.3},
    })
    assert result["valid"] is True
    assert result["warnings"]
