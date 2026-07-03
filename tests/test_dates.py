from scraper.dates import extract_deadline


def test_extracts_month_day_year_after_closes_on():
    text = (
        "Submit before the deadline. The application window closes on "
        "July 31, 2026. Incomplete or late submissions will not be processed."
    )
    deadline, raw = extract_deadline(text, reference_date="2026-07-04")
    assert deadline == "2026-07-31"
    assert "July 31, 2026" in raw


def test_extracts_deadline_colon_phrasing():
    text = "Deadline: August 30, 2026. Apply now via the online portal."
    deadline, raw = extract_deadline(text, reference_date="2026-07-04")
    assert deadline == "2026-08-30"
    assert "August 30, 2026" in raw


def test_extracts_apply_on_or_before_phrasing():
    text = "Apply on or before Aug. 15, 2026 to be considered."
    deadline, raw = extract_deadline(text, reference_date="2026-07-04")
    assert deadline == "2026-08-15"


def test_returns_none_when_no_date_present():
    text = "Applications are accepted until slots are filled."
    deadline, raw = extract_deadline(text, reference_date="2026-07-04")
    assert deadline is None
    assert raw == ""


def test_bare_month_day_without_year_is_not_guessed():
    text = "Deadline: August 30. Apply now."
    deadline, raw = extract_deadline(text, reference_date="2026-07-04")
    assert deadline is None
    assert raw == ""


def test_no_text_returns_none():
    deadline, raw = extract_deadline("", reference_date="2026-07-04")
    assert deadline is None
    assert raw == ""
