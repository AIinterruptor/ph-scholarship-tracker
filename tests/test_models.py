from scraper.models import make_grant


def test_make_grant_normalizes_whitespace_and_sets_dates():
    grant = make_grant(
        title="  CHED   EASE  Scholarship  \n",
        description="Covers tuition.\n\n  ",
        deadline="2026-07-31",
        deadline_text=" The application window closes on July 31, 2026. ",
        url="https://assistance.ph/ched-ease-scholarship/",
        category="government",
        level="undergrad",
        source="assistance.ph",
        scrape_date="2026-07-04",
    )
    assert grant == {
        "title": "CHED EASE Scholarship",
        "description": "Covers tuition.",
        "deadline": "2026-07-31",
        "deadline_text": "The application window closes on July 31, 2026.",
        "url": "https://assistance.ph/ched-ease-scholarship/",
        "category": "government",
        "level": "undergrad",
        "source": "assistance.ph",
        "is_manual": False,
        "first_seen": "2026-07-04",
        "last_seen": "2026-07-04",
    }


def test_make_grant_allows_null_deadline():
    grant = make_grant(
        title="Some Grant",
        description="desc",
        deadline=None,
        deadline_text="",
        url="https://example.com",
        category="private",
        level="undergrad",
        source="Example",
        scrape_date="2026-07-04",
    )
    assert grant["deadline"] is None
    assert grant["deadline_text"] == ""
