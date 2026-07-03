from pathlib import Path

from scraper.parsers import assistance_ph

FIXTURES = Path(__file__).parent / "fixtures"


def _read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_extracts_scholarship_listing_with_deadline():
    listing_html = _read_fixture("assistance_ph_listing.html")
    detail_html = _read_fixture("assistance_ph_detail_ched_ease.html")

    def fake_fetch(url):
        assert url == "https://assistance.ph/ched-ease-scholarship/"
        return detail_html

    grants = assistance_ph.parse(fake_fetch, listing_html, scrape_date="2026-07-04")

    assert len(grants) == 1
    grant = grants[0]
    assert grant["title"] == (
        "CHED EASE Scholarship Open for AY 2026-2027: "
        "Up to PHP60,000 Educational Allowance"
    )
    assert grant["url"] == "https://assistance.ph/ched-ease-scholarship/"
    assert grant["source"] == "assistance.ph"
    assert grant["deadline"] == "2026-07-31"
    assert "July 31, 2026" in grant["deadline_text"]
    assert grant["description"] != ""


def test_parse_skips_non_scholarship_listings():
    listing_html = _read_fixture("assistance_ph_listing.html")

    def fake_fetch(url):
        raise AssertionError(f"should not fetch non-scholarship URL {url}")

    grants = assistance_ph.parse(fake_fetch, listing_html, scrape_date="2026-07-04")

    titles = [g["title"] for g in grants]
    assert not any("DMW" in t for t in titles)


def test_parse_handles_detail_page_with_no_deadline():
    listing_html = """
    <article><header class="entry-header"><h2 class="entry-title">
    <a href="https://assistance.ph/some-scholarship-grant/">Some Scholarship Grant</a>
    </h2></header></article>
    """
    detail_html = _read_fixture("assistance_ph_detail_no_deadline.html")

    def fake_fetch(url):
        return detail_html

    grants = assistance_ph.parse(fake_fetch, listing_html, scrape_date="2026-07-04")

    assert len(grants) == 1
    assert grants[0]["deadline"] is None
    assert grants[0]["deadline_text"] == ""


def test_parse_skips_listing_when_detail_fetch_fails():
    listing_html = _read_fixture("assistance_ph_listing.html")

    def failing_fetch(url):
        if "ched-ease" in url:
            raise ConnectionError("boom")
        return _read_fixture("assistance_ph_detail_no_deadline.html")

    grants = assistance_ph.parse(failing_fetch, listing_html, scrape_date="2026-07-04")

    assert all("CHED EASE" not in g["title"] for g in grants)
