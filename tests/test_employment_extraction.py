from datetime import date

from app.resume_intelligence import (
    _parse_month_year,
    _date_range_from_line,
    _calculate_cumulative_experience,
    _extract_employment_intervals,
)


CURRENT_DATE = date(2026, 11, 20)


def test_parse_month_year():
    assert _parse_month_year("Jan 2023", CURRENT_DATE) == (2023, 1)


def test_parse_numeric_month_year():
    assert _parse_month_year("06/2024", CURRENT_DATE) == (2024, 6)


def test_parse_year_only():
    assert _parse_month_year("2022", CURRENT_DATE) == (2022, 1)


def test_parse_present():
    assert _parse_month_year("Present", CURRENT_DATE) == (2026, 11)


def test_month_year_date_range():
    result = _date_range_from_line(
        "Software Engineer | Jan 2022 - Dec 2023",
        CURRENT_DATE,
    )

    assert result == ((2022, 1), (2023, 12))


def test_numeric_date_range():
    result = _date_range_from_line(
        "Developer | 01/2023 - 06/2024",
        CURRENT_DATE,
    )

    assert result == ((2023, 1), (2024, 6))


def test_year_date_range():
    result = _date_range_from_line(
        "Analyst | 2022 - 2024",
        CURRENT_DATE,
    )

    assert result == ((2022, 1), (2024, 1))


def test_overlapping_intervals():
    intervals = [
        ((2020, 1), (2022, 12)),
        ((2021, 1), (2023, 12)),
    ]

    assert _calculate_cumulative_experience(intervals) == 4.0


def test_non_overlapping_intervals():
    intervals = [
        ((2020, 1), (2021, 12)),
        ((2022, 1), (2023, 12)),
    ]

    assert _calculate_cumulative_experience(intervals) == 4.0


def test_empty_intervals():
    assert _calculate_cumulative_experience([]) is None


def test_employment_entry_detection():

    lines = [
        "Software Engineer",
        "ABC Technologies",
        "Jan 2022 - Dec 2023",
    ]

    professional, internships, _, _, ambiguous = (
        _extract_employment_intervals(
            lines,
            CURRENT_DATE,
        )
    )

    assert len(professional) == 1
    assert len(internships) == 0
    assert len(ambiguous) == 0


def test_internship_classification():

    lines = [
        "Machine Learning Intern",
        "ABC Technologies",
        "Jan 2023 - Jun 2023",
    ]

    professional, internships, _, _, _ = (
        _extract_employment_intervals(
            lines,
            CURRENT_DATE,
        )
    )

    assert len(professional) == 0
    assert len(internships) == 1