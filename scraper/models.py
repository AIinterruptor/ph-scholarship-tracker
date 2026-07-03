import re


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def make_grant(
    title,
    description,
    deadline,
    deadline_text,
    url,
    category,
    level,
    source,
    scrape_date,
):
    return {
        "title": _clean(title),
        "description": _clean(description),
        "deadline": deadline,
        "deadline_text": _clean(deadline_text) if deadline_text else "",
        "url": url,
        "category": category,
        "level": level,
        "source": source,
        "is_manual": False,
        "first_seen": scrape_date,
        "last_seen": scrape_date,
    }
