from app.resume_intelligence import (
    _calculate_cumulative_experience,
)


def test_non_overlapping_experience():

    intervals = [
        ((2020, 1), (2021, 12)),
        ((2022, 1), (2023, 12)),
    ]

    assert _calculate_cumulative_experience(intervals) == 4.0


def test_overlapping_experience():

    intervals = [
        ((2020, 1), (2022, 12)),
        ((2021, 1), (2023, 12)),
    ]

    assert _calculate_cumulative_experience(intervals) == 4.0


def test_fully_overlapping_experience():

    intervals = [
        ((2020, 1), (2022, 12)),
        ((2020, 1), (2022, 12)),
    ]

    assert _calculate_cumulative_experience(intervals) == 3.0


def test_empty_experience():

    assert _calculate_cumulative_experience([]) is None