import json
from datetime import date, datetime
from pathlib import Path

from scraper.http import fetch
from scraper.sources import SOURCES

DATA_DIR = Path(__file__).parent.parent / "data"
GRANTS_PATH = DATA_DIR / "grants.json"
ERRORS_PATH = DATA_DIR / "last_run_errors.json"
NULL_DEADLINE_EXPIRY_DAYS = 14


def _dedup_key(grant: dict) -> tuple:
    return (grant["source"], grant["title"])


def _days_between(earlier: str, later: str) -> int:
    return (datetime.fromisoformat(later) - datetime.fromisoformat(earlier)).days


def _is_retained(grant: dict, scrape_date: str) -> bool:
    if grant["deadline"] is not None:
        return grant["deadline"] >= scrape_date
    return _days_between(grant["last_seen"], scrape_date) <= NULL_DEADLINE_EXPIRY_DAYS


def merge_grants(existing: list, freshly_scraped: list, scrape_date: str) -> list:
    by_key = {_dedup_key(grant): dict(grant) for grant in existing}

    for grant in freshly_scraped:
        key = _dedup_key(grant)
        if key in by_key:
            by_key[key]["last_seen"] = scrape_date
            if grant["deadline"] is not None or by_key[key]["deadline"] is None:
                by_key[key]["deadline"] = grant["deadline"]
                by_key[key]["deadline_text"] = grant["deadline_text"]
        else:
            by_key[key] = dict(grant)

    kept = [grant for grant in by_key.values() if _is_retained(grant, scrape_date)]
    kept.sort(key=lambda g: (g["deadline"] is None, g["deadline"] or "", g["first_seen"]))
    return kept


def run(scrape_date: str) -> tuple:
    freshly_scraped = []
    errors = []

    for source in SOURCES:
        try:
            listing_html = fetch(source["url"])
            grants = source["parser"](fetch, listing_html, scrape_date)
            freshly_scraped.extend(grants)
        except Exception as exc:  # noqa: BLE001 - any source failure must not stop the run
            errors.append(
                {
                    "source": source["name"],
                    "url": source["url"],
                    "error": str(exc),
                    "timestamp": scrape_date,
                }
            )

    existing = []
    if GRANTS_PATH.exists():
        existing = json.loads(GRANTS_PATH.read_text(encoding="utf-8"))

    merged = merge_grants(existing, freshly_scraped, scrape_date)
    return merged, errors


if __name__ == "__main__":
    today = date.today().isoformat()
    grants, errors = run(today)
    DATA_DIR.mkdir(exist_ok=True)
    GRANTS_PATH.write_text(json.dumps(grants, indent=2, ensure_ascii=False), encoding="utf-8")
    ERRORS_PATH.write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(grants)} grants, {len(errors)} source errors.")
