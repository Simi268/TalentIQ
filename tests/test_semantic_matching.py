import numpy as np
import pytest

from app.semantic_matching import (
    normalize_skill,
    get_candidate_skills,
    cosine_similarity,
    calculate_semantic_similarity,
    find_related_skills,
    match_requirement,
    match_candidate,
)


class FakeEmbeddingModel:
    """
    Deterministic embedding model for unit testing.
    No external model download required.
    """

    def encode(
        self,
        sentences,
        convert_to_numpy=True,
        normalize_embeddings=False
    ):

        vectors = {

            "python": [1.0, 0.0, 0.0],

            "python development": [0.99, 0.01, 0.0],

            "unrelated topic": [0.0, 1.0, 0.0],

            "machine learning": [0.8, 0.2, 0.0],

        }

        return np.array([
            vectors.get(
                sentence.lower(),
                [0.0, 0.0, 1.0]
            )
            for sentence in sentences
        ])


def test_skill_normalization():

    assert normalize_skill("ML") == "machine learning"

    assert normalize_skill("Postgre SQL") == "postgresql"

    assert normalize_skill("Python") == "python"


def test_candidate_skill_extraction():

    profile = {

        "skills": [

            "Python",

            "SQL",

            "FastAPI",

            {"name": "Docker"}

        ]

    }

    skills = get_candidate_skills(profile)

    assert "python" in skills

    assert "sql" in skills

    assert "fastapi" in skills

    assert "docker" in skills


def test_cosine_similarity_identical_vectors():

    vector = np.array([1.0, 0.0, 0.0])

    assert cosine_similarity(
        vector,
        vector
    ) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():

    a = np.array([1.0, 0.0])

    b = np.array([0.0, 1.0])

    assert cosine_similarity(a, b) == 0.0


def test_zero_vector_similarity():

    a = np.array([0.0, 0.0])

    b = np.array([1.0, 0.0])

    assert cosine_similarity(a, b) == 0.0


def test_semantic_similarity():

    model = FakeEmbeddingModel()

    score = calculate_semantic_similarity(
        "python",
        "python development",
        model
    )

    assert score > 0.99


def test_empty_semantic_input():

    assert calculate_semantic_similarity(
        "",
        "python"
    ) == 0.0


def test_related_skill_detection():

    result = find_related_skills(
        "natural language processing",
        ["BERT", "Python"]
    )

    assert "bert" in result


def test_exact_skill_match():

    result = match_requirement(
        "Python",
        ["Python", "SQL"],
        []
    )

    assert result["status"] == "exact_match"

    assert result["similarity"] == 1.0


def test_related_skill_is_not_exact_match():

    result = match_requirement(
        "NLP",
        ["BERT"],
        ["Built a BERT-based text classifier"]
    )

    assert result["status"] == "related_match"

    assert result["match_type"] == "related"


def test_semantic_match_requires_verification():

    model = FakeEmbeddingModel()

    result = match_requirement(
        "Python",
        [],
        ["python development"],
        model=model
    )

    assert result["status"] == "needs_verification"


def test_unverified_skill():

    model = FakeEmbeddingModel()

    result = match_requirement(
        "Docker",
        ["Python"],
        [],
        model=model
    )

    assert result["status"] == "unverified"


def test_complete_candidate_matching():

    jd = {

        "required_skills": [
            "Python",
            "SQL"
        ],

        "preferred_skills": [
            "Docker"
        ]

    }

    profile = {

        "skills": [
            "Python",
            "SQL"
        ],

        "experience_evidence": [
            "Developed Python applications"
        ]

    }

    result = match_candidate(
        jd,
        profile
    )

    stats = result["statistics"]

    assert stats["total_requirements"] == 3

    assert stats["exact_matches"] == 2

    assert stats["unverified"] == 1


def test_matching_does_not_invent_evidence():

    result = match_requirement(
        "Docker",
        [],
        []
    )

    assert result["supporting_evidence"] == []

    assert result["status"] == "unverified"