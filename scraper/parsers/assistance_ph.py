from bs4 import BeautifulSoup

from scraper.dates import extract_deadline
from scraper.models import make_grant

SOURCE_NAME = "assistance.ph"
_SCHOLARSHIP_KEYWORDS = ("scholar",)


def _is_scholarship_listing(title: str) -> bool:
    lowered = title.lower()
    return any(keyword in lowered for keyword in _SCHOLARSHIP_KEYWORDS)


def parse(fetch_fn, listing_html: str, scrape_date: str) -> list:
    soup = BeautifulSoup(listing_html, "html.parser")
    grants = []

    for header in soup.select("h2.entry-title"):
        link = header.select_one("h2.entry-title a") or header.select_one("a")
        if link is None:
            continue
        title = link.get_text(" ", strip=True)
        url = link.get("href", "")
        if not title or not url or not _is_scholarship_listing(title):
            continue

        try:
            detail_html = fetch_fn(url)
        except Exception:
            continue

        detail_soup = BeautifulSoup(detail_html, "html.parser")
        content = detail_soup.select_one("div.entry-content")
        content_text = content.get_text(" ", strip=True) if content else ""
        description = content.find("p").get_text(" ", strip=True) if content and content.find("p") else ""
        deadline, deadline_text = extract_deadline(content_text, reference_date=scrape_date)

        grants.append(
            make_grant(
                title=title,
                description=description,
                deadline=deadline,
                deadline_text=deadline_text,
                url=url,
                category="private",
                level="undergrad",
                source=SOURCE_NAME,
                scrape_date=scrape_date,
            )
        )

    return grants
