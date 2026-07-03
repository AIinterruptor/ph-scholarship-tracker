from scraper.scrape import merge_grants


def _grant(title, first_seen, last_seen, deadline=None, deadline_text="", source="Test Source"):
    return {
        "title": title,
        "description": "desc",
        "deadline": deadline,
        "deadline_text": deadline_text,
        "url": "https://example.com",
        "category": "private",
        "level": "undergrad",
        "source": source,
        "is_manual": False,
        "first_seen": first_seen,
        "last_seen": last_seen,
    }


def test_new_grant_is_added():
    result = merge_grants([], [_grant("New Grant", "2026-07-04", "2026-07-04")], scrape_date="2026-07-04")
    assert len(result) == 1
    assert result[0]["title"] == "New Grant"


def test_reseen_grant_updates_last_seen_and_deadline_but_keeps_first_seen():
    existing = [_grant("Annual Grant", "2025-06-01", "2025-06-01", deadline="2025-08-30", deadline_text="August 30, 2025")]
    fresh = [_grant("Annual Grant", "2026-07-04", "2026-07-04", deadline="2026-08-30", deadline_text="August 30, 2026")]
    result = merge_grants(existing, fresh, scrape_date="2026-07-04")
    assert len(result) == 1
    assert result[0]["first_seen"] == "2025-06-01"
    assert result[0]["last_seen"] == "2026-07-04"
    assert result[0]["deadline"] == "2026-08-30"
    assert result[0]["deadline_text"] == "August 30, 2026"


def test_grant_with_passed_deadline_is_dropped():
    existing = [_grant("Expired Grant", "2026-06-01", "2026-06-01", deadline="2026-07-01", deadline_text="July 1, 2026")]
    result = merge_grants(existing, [], scrape_date="2026-07-04")
    assert result == []


def test_grant_with_future_deadline_is_kept_even_if_unseen_long_ago():
    existing = [_grant("Open Grant", "2026-01-01", "2026-01-01", deadline="2026-12-31", deadline_text="December 31, 2026")]
    result = merge_grants(existing, [], scrape_date="2026-07-04")
    assert len(result) == 1


def test_null_deadline_grant_dropped_after_14_days_unseen():
    existing = [_grant("Rolling Grant", "2026-06-01", "2026-06-10")]
    result = merge_grants(existing, [], scrape_date="2026-06-25")
    assert result == []


def test_null_deadline_grant_kept_within_14_days_unseen():
    existing = [_grant("Rolling Grant", "2026-06-01", "2026-06-10")]
    result = merge_grants(existing, [], scrape_date="2026-06-24")
    assert len(result) == 1


def test_result_sorted_ascending_by_deadline_nulls_last():
    existing = [
        _grant("No Deadline", "2026-07-01", "2026-07-01"),
        _grant("Later Deadline", "2026-07-01", "2026-07-01", deadline="2026-09-30", deadline_text="Sep 30"),
        _grant("Sooner Deadline", "2026-07-01", "2026-07-01", deadline="2026-08-01", deadline_text="Aug 1"),
    ]
    result = merge_grants(existing, [], scrape_date="2026-07-01")
    assert [g["title"] for g in result] == ["Sooner Deadline", "Later Deadline", "No Deadline"]


def test_reseen_grant_with_null_fresh_deadline_preserves_existing_deadline():
    existing = [_grant("Flaky Extraction Grant", "2026-01-01", "2026-01-01", deadline="2026-08-30", deadline_text="August 30, 2026")]
    fresh = [_grant("Flaky Extraction Grant", "2026-07-04", "2026-07-04", deadline=None, deadline_text="")]
    result = merge_grants(existing, fresh, scrape_date="2026-07-04")
    assert len(result) == 1
    assert result[0]["deadline"] == "2026-08-30"
    assert result[0]["deadline_text"] == "August 30, 2026"
    assert result[0]["last_seen"] == "2026-07-04"


def test_reseen_grant_with_no_prior_deadline_and_null_fresh_deadline_stays_null():
    existing = [_grant("Rolling Grant", "2026-01-01", "2026-01-01")]
    fresh = [_grant("Rolling Grant", "2026-07-04", "2026-07-04")]
    result = merge_grants(existing, fresh, scrape_date="2026-07-04")
    assert len(result) == 1
    assert result[0]["deadline"] is None
