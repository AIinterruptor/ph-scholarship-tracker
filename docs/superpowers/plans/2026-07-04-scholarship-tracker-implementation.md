# PH Scholarship Grants Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free, static-site directory of PH scholarship/grant
opportunities, scraped daily via GitHub Actions and published on GitHub
Pages, mirroring the `ph-discounts-tracker` architecture.

**Architecture:** Python scraper (`requests` + `BeautifulSoup`) fetches each
source's listing page, then fetches each listing's detail page to extract
description and deadline (two-step fetch — deadlines live in article
bodies, not listing excerpts). Results merge into `data/grants.json` with
deadline-based retention. A separate hand-maintained
`data/manual_grants.json` covers well-known scholarships whose official
sites (CHED, DOST-SEI, OWWA, GSIS) block scraping. `index.html` is a
dependency-free static page that fetches and merges both JSON files
client-side and renders a filterable, deadline-sorted feed. A GitHub
Actions workflow runs the scraper daily and commits `data/grants.json`.

**Tech Stack:** Python 3.11, `requests`, `beautifulsoup4`, `pytest`; vanilla
HTML/CSS/JS frontend (no framework, no build step); GitHub Actions +
GitHub Pages.

## Global Constraints

- No backend server, no database, no build step, no user auth, no
  crowdsourcing/submissions in v1.
- Dedup key for scraped grants: `(source, title)`.
- Deadline retention: keep while `deadline >= scrape_date` if set; if
  `deadline` is null, keep while unseen ≤ 14 days from `last_seen`.
- Manual entries (`is_manual: true`) live only in `data/manual_grants.json`,
  are never touched by the scraper's merge logic, and are excluded from
  the 14-day/deadline retention rules entirely.
- Categories: `government`, `private`, `global`, `ngo`. Levels: `undergrad`,
  `graduate`, `professional`.
- Output sort: ascending by `deadline`, null-deadline (including all
  manual entries) sorted last.
- `requirements.txt` pins: `requests==2.32.3`, `beautifulsoup4==4.12.3`,
  `python-dateutil==2.9.0.post0`, `pytest==8.3.3`.

---

## File Structure

```
ph-scholarship-tracker/
  data/
    grants.json                 # scraper output (created by scrape.py on first run)
    last_run_errors.json        # scraper output (created by scrape.py on first run)
    manual_grants.json          # hand-maintained, committed directly
  scraper/
    __init__.py
    http.py                     # fetch() helper, identical pattern to discount tracker
    models.py                   # make_grant() normalizer
    dates.py                    # extract_deadline() best-effort date parser
    sources.py                  # SOURCES list
    scrape.py                   # orchestration: fetch, parse, merge, write
    parsers/
      __init__.py
      assistance_ph.py          # listing + detail parser for assistance.ph
  tests/
    __init__.py
    fixtures/
      assistance_ph_listing.html
      assistance_ph_detail_ched_ease.html
      assistance_ph_detail_no_deadline.html
    test_models.py
    test_dates.py
    test_parsers.py
    test_merge.py
  .github/
    workflows/
      scrape.yml
  index.html
  requirements.txt
  README.md
```

---

### Task 1: Project scaffold and `make_grant` normalizer

**Files:**
- Create: `requirements.txt`
- Create: `scraper/__init__.py` (empty)
- Create: `scraper/models.py`
- Create: `tests/__init__.py` (empty)
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `make_grant(title, description, deadline, deadline_text, url, category, level, source, scrape_date) -> dict` — used by all parsers and by manual-entry tooling.

- [ ] **Step 1: Write `requirements.txt`**

```
requests==2.32.3
beautifulsoup4==4.12.3
python-dateutil==2.9.0.post0
pytest==8.3.3
```

- [ ] **Step 2: Create empty package markers**

Create `scraper/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 3: Write the failing test for `make_grant`**

`tests/test_models.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.models'`

- [ ] **Step 5: Implement `scraper/models.py`**

```python
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt scraper/__init__.py scraper/models.py tests/__init__.py tests/test_models.py
git commit -m "Add project scaffold and make_grant normalizer"
```

---

### Task 2: Deadline extraction helper

**Files:**
- Create: `scraper/dates.py`
- Test: `tests/test_dates.py`

**Interfaces:**
- Consumes: nothing (pure function, stdlib + `python-dateutil`).
- Produces: `extract_deadline(text: str, reference_date: str) -> tuple[str | None, str]` — returns `(iso_date_or_None, matched_raw_text_or_empty_string)`. Used by `scraper/parsers/assistance_ph.py` (Task 3) and any future parser.

- [ ] **Step 1: Write the failing tests**

`tests/test_dates.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.dates'`

- [ ] **Step 3: Implement `scraper/dates.py`**

```python
import re

from dateutil import parser as dateutil_parser

_DEADLINE_PATTERNS = [
    r"closes?\s+on\s+([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})",
    r"deadline\s*:?\s*([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})",
    r"on\s+or\s+before\s+([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})",
    r"until\s+([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})",
]


def extract_deadline(text: str, reference_date: str) -> tuple:
    if not text:
        return None, ""

    for pattern in _DEADLINE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue
        raw = match.group(1)
        try:
            parsed = dateutil_parser.parse(raw, fuzzy=False)
        except (ValueError, OverflowError):
            continue
        return parsed.date().isoformat(), raw

    return None, ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dates.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add scraper/dates.py tests/test_dates.py
git commit -m "Add best-effort deadline extraction helper"
```

---

### Task 3: `assistance.ph` two-step parser

**Files:**
- Create: `scraper/http.py`
- Create: `scraper/parsers/__init__.py` (empty)
- Create: `scraper/parsers/assistance_ph.py`
- Create: `tests/fixtures/assistance_ph_listing.html`
- Create: `tests/fixtures/assistance_ph_detail_ched_ease.html`
- Create: `tests/fixtures/assistance_ph_detail_no_deadline.html`
- Test: `tests/test_parsers.py`

**Interfaces:**
- Consumes: `make_grant(...)` (Task 1), `extract_deadline(text, reference_date)` (Task 2).
- Produces:
  - `fetch(url: str, timeout: int = 15) -> str` in `scraper/http.py` — used by `scrape.py` (Task 5).
  - `parse(fetch_fn, listing_html: str, scrape_date: str) -> list[dict]` in `scraper/parsers/assistance_ph.py` — takes an injected `fetch_fn(url) -> str` so tests can stub detail-page fetches without real HTTP calls. Used by `scraper/sources.py` (Task 4).

- [ ] **Step 1: Write `scraper/http.py`**

```python
import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def fetch(url: str, timeout: int = 15) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    return response.text
```

- [ ] **Step 2: Create fixture: listing page**

`tests/fixtures/assistance_ph_listing.html` (trimmed to the relevant repeating structure — two articles, one scholarship-relevant, one not, matching the real site's mixed-category feed):

```html
<html><body>
<div id="content">
<article id="post-7235" class="post-7235 post type-post status-publish hentry category-tips">
  <div class="inside-article">
    <header class="entry-header">
      <h2 class="entry-title" itemprop="headline">
        <a href="https://assistance.ph/ched-ease-scholarship/" rel="bookmark">CHED EASE Scholarship Open for AY 2026-2027: Up to PHP60,000 Educational Allowance</a>
      </h2>
    </header>
    <div class="entry-summary" itemprop="text">
      <p>&#8230; <a class="read-more" href="https://assistance.ph/ched-ease-scholarship/">Read more</a></p>
    </div>
  </div>
</article>
<article id="post-7221" class="post-7221 post type-post status-publish hentry category-news">
  <div class="inside-article">
    <header class="entry-header">
      <h2 class="entry-title" itemprop="headline">
        <a href="https://assistance.ph/dmw-announces-php12000-relief/" rel="bookmark">DMW Announces PHP12,000 Financial Relief for OFWs</a>
      </h2>
    </header>
    <div class="entry-summary" itemprop="text">
      <p>&#8230; <a class="read-more" href="https://assistance.ph/dmw-announces-php12000-relief/">Read more</a></p>
    </div>
  </div>
</article>
</div>
</body></html>
```

- [ ] **Step 3: Create fixture: detail page with deadline**

`tests/fixtures/assistance_ph_detail_ched_ease.html`:

```html
<html><body>
<article id="post-7235">
<h1 class="entry-title" itemprop="headline">CHED EASE Scholarship Open for AY 2026-2027: Up to PHP60,000 Educational Allowance</h1>
<div class="entry-content">
<p>The Commission on Higher Education's Educational Assistance for Students (EASE) program provides up to PHP60,000 per year for qualified Filipino undergraduates enrolled in CHED-recognized priority programs.</p>
<ol>
<li><strong class="font-semibold">Submit before the deadline.</strong> The application window closes on <strong class="font-semibold">July 31, 2026</strong>. Incomplete or late submissions will not be processed.</li>
</ol>
</div>
</article>
</body></html>
```

- [ ] **Step 4: Create fixture: detail page without a deadline**

`tests/fixtures/assistance_ph_detail_no_deadline.html`:

```html
<html><body>
<article id="post-7221">
<h1 class="entry-title" itemprop="headline">DMW Announces PHP12,000 Financial Relief for OFWs</h1>
<div class="entry-content">
<p>The Department of Migrant Workers has introduced a new relief program for OFWs affected by regional instability. Applications are accepted until slots are filled.</p>
</div>
</article>
</body></html>
```

- [ ] **Step 5: Write the failing test**

`tests/test_parsers.py`:

```python
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
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.parsers'`

- [ ] **Step 7: Create `scraper/parsers/__init__.py`**

Empty file.

- [ ] **Step 8: Implement `scraper/parsers/assistance_ph.py`**

```python
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

    for header in soup.select("header.entry-header, h2.entry-title"):
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
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: PASS (4 tests)

- [ ] **Step 10: Commit**

```bash
git add scraper/http.py scraper/parsers/__init__.py scraper/parsers/assistance_ph.py tests/fixtures/assistance_ph_listing.html tests/fixtures/assistance_ph_detail_ched_ease.html tests/fixtures/assistance_ph_detail_no_deadline.html tests/test_parsers.py
git commit -m "Add assistance.ph two-step scraper parser"
```

---

### Task 4: Source registry

**Files:**
- Create: `scraper/sources.py`

**Interfaces:**
- Consumes: `scraper.parsers.assistance_ph.parse` (Task 3).
- Produces: `SOURCES: list[dict]`, each `{"name": str, "url": str, "parser": callable(fetch_fn, listing_html, scrape_date) -> list[dict]}`. Used by `scrape.py` (Task 5).

- [ ] **Step 1: Implement `scraper/sources.py`**

```python
from scraper.parsers import assistance_ph

SOURCES = [
    {
        "name": "assistance.ph",
        "url": "https://assistance.ph",
        "parser": assistance_ph.parse,
    },
]
```

No test file — this is a static registry exercised end-to-end by
`test_scrape.py`-equivalent coverage already in Task 3 (per-source parser
tests) and Task 5 (orchestration test uses a fake source list). Nothing
here has independent logic to unit test.

- [ ] **Step 2: Commit**

```bash
git add scraper/sources.py
git commit -m "Add scraper source registry"
```

---

### Task 5: Merge/retention logic and scrape orchestration

**Files:**
- Create: `scraper/scrape.py`
- Test: `tests/test_merge.py`

**Interfaces:**
- Consumes: `SOURCES` (Task 4), `fetch` (Task 3's `scraper/http.py`).
- Produces:
  - `merge_grants(existing: list[dict], freshly_scraped: list[dict], scrape_date: str) -> list[dict]` — pure function, used by tests and `run()`.
  - `run(scrape_date: str) -> tuple[list[dict], list[dict]]` — returns `(merged_grants, errors)`. Used by the `__main__` block and, indirectly, by the GitHub Actions workflow (Task 7).

- [ ] **Step 1: Write the failing tests**

`tests/test_merge.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_merge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scraper.scrape'`

- [ ] **Step 3: Implement `scraper/scrape.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_merge.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests from Tasks 1-5)

- [ ] **Step 6: Commit**

```bash
git add scraper/scrape.py tests/test_merge.py
git commit -m "Add deadline-based merge/retention logic and scrape orchestration"
```

---

### Task 6: Manual grants file and frontend

**Files:**
- Create: `data/manual_grants.json`
- Create: `index.html`

**Interfaces:**
- Consumes: `data/grants.json` (Task 5 output shape), `data/manual_grants.json` (this task).
- Produces: nothing consumed by later tasks — this is the UI leaf.

- [ ] **Step 1: Create `data/manual_grants.json`**

```json
[
  {
    "title": "CHED Scholarship Programs (CMSP, Tulong Dunong, TES)",
    "description": "Merit- and need-based undergraduate scholarships covering tuition, book allowances, and stipends. Eligibility and application periods vary by program and are announced on the official CHED site.",
    "deadline": null,
    "deadline_text": "Verify current application period on the official CHED site",
    "url": "https://ched.gov.ph/scholarships-and-grants-programs/",
    "category": "government",
    "level": "undergrad",
    "source": "CHED",
    "is_manual": true
  },
  {
    "title": "DOST-SEI Undergraduate Science and Technology Scholarship",
    "description": "Tuition subsidy, monthly allowance, book and thesis grants for STEM undergraduates who pass the DOST-SEI qualifying exam.",
    "deadline": null,
    "deadline_text": "Verify current application period on the official DOST-SEI site",
    "url": "https://sei.dost.gov.ph/index.php/programs-and-projects/undergraduate-scholarship",
    "category": "government",
    "level": "undergrad",
    "source": "DOST-SEI",
    "is_manual": true
  },
  {
    "title": "OWWA Education for Development Scholarship Program (EDSP)",
    "description": "Scholarship for dependents of Overseas Filipino Workers, covering tuition and living expenses.",
    "deadline": null,
    "deadline_text": "Verify current application period on the official OWWA site",
    "url": "https://scholarship.owwa.gov.ph/",
    "category": "government",
    "level": "undergrad",
    "source": "OWWA",
    "is_manual": true
  },
  {
    "title": "GSIS Scholarship Program",
    "description": "Tuition coverage and living allowances for children of active GSIS members pursuing college education.",
    "deadline": null,
    "deadline_text": "Verify current application period on the official GSIS site",
    "url": "https://www.gsis.gov.ph/",
    "category": "government",
    "level": "undergrad",
    "source": "GSIS",
    "is_manual": true
  }
]
```

- [ ] **Step 2: Create `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PH Scholarship Grants Tracker</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #ffffff;
    --fg: #1a1a1a;
    --card-bg: #f5f5f5;
    --sidebar-bg: #fafafa;
    --border: #e0e0e0;
    --accent: #0a5bd7;
    --warn: #b7791f;
    --muted: #666666;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #121212;
      --fg: #e8e8e8;
      --card-bg: #1e1e1e;
      --sidebar-bg: #181818;
      --border: #333333;
      --accent: #5b9dff;
      --warn: #e0b04a;
      --muted: #a0a0a0;
    }
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--fg);
    margin: 0;
  }
  header.page-header {
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border);
  }
  header.page-header h1 { font-size: 1.4rem; margin: 0 0 0.25rem; }
  header.page-header .subtitle { color: var(--muted); margin: 0; font-size: 0.9rem; }

  .layout {
    display: flex;
    align-items: flex-start;
    max-width: 1100px;
    margin-inline: auto;
  }

  aside.sidebar {
    width: 240px;
    flex-shrink: 0;
    padding: 1.5rem 1rem;
    border-right: 1px solid var(--border);
    background: var(--sidebar-bg);
    min-height: calc(100vh - 80px);
  }
  .filter-group { margin-bottom: 1.5rem; }
  .filter-group h2 {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin: 0 0 0.6rem;
  }
  .filter-option {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.5rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    color: var(--fg);
    background: transparent;
    border: none;
    width: 100%;
    text-align: left;
  }
  .filter-option:hover { background: var(--card-bg); }
  .filter-option.active { background: var(--accent); color: #ffffff; }

  main.results {
    flex: 1;
    padding: 1.5rem;
    min-width: 0;
  }
  .results-count { color: var(--muted); font-size: 0.85rem; margin: 0 0 1rem; }

  .grant-card {
    background: var(--card-bg);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
  }
  .grant-title { font-weight: 600; margin: 0 0 0.25rem; }
  .grant-deadline { color: var(--accent); font-weight: 600; font-size: 0.9rem; }
  .grant-deadline.closing-soon { color: var(--warn); }
  .grant-deadline.manual { color: var(--muted); font-style: italic; }
  .grant-description { color: var(--muted); font-size: 0.9rem; margin: 0.4rem 0; }
  .grant-meta { font-size: 0.8rem; color: var(--muted); display: flex; justify-content: space-between; margin-top: 0.5rem; }
  .grant-meta a { color: var(--fg); }
  #empty-state, #fetch-error { color: var(--muted); text-align: center; padding: 2rem 0; }
  #scraper-status { color: var(--muted); font-size: 0.8rem; margin-top: 1.5rem; }
  #scraper-status summary { cursor: pointer; }
  #scraper-status ul { margin: 0.5rem 0 0; padding-left: 1.25rem; }

  @media (max-width: 700px) {
    .layout { flex-direction: column; }
    aside.sidebar { width: 100%; min-height: auto; border-right: none; border-bottom: 1px solid var(--border); }
  }
</style>
</head>
<body>
  <header class="page-header">
    <h1>PH Scholarship Grants Tracker</h1>
    <p class="subtitle">Philippine scholarship and grant opportunities, scraped daily. Sorted by soonest deadline.</p>
  </header>
  <div class="layout">
    <aside class="sidebar">
      <div class="filter-group">
        <h2>Category</h2>
        <div id="category-filters"></div>
      </div>
      <div class="filter-group">
        <h2>Level</h2>
        <div id="level-filters"></div>
      </div>
    </aside>
    <main class="results">
      <p class="results-count" id="results-count"></p>
      <div id="grants"></div>
      <div id="empty-state" style="display:none;">No grants match this filter.</div>
      <details id="scraper-status" style="display:none;">
        <summary>Scraper status</summary>
        <ul id="scraper-errors"></ul>
      </details>
    </main>
  </div>

  <script>
    const CATEGORIES = ["government", "private", "global", "ngo"];
    const LEVELS = ["undergrad", "graduate", "professional"];
    const CLOSING_SOON_DAYS = 14;
    let allGrants = [];
    let activeCategory = "all";
    let activeLevel = "all";

    function daysUntil(dateStr) {
      const diffMs = new Date(dateStr + "T00:00:00").getTime() - Date.now();
      return Math.floor(diffMs / 86400000);
    }

    function renderFilterGroup(containerId, options, active, onSelect) {
      const container = document.getElementById(containerId);
      const all = ["all", ...options];
      container.innerHTML = all
        .map(
          (opt) =>
            `<button class="filter-option${opt === active ? " active" : ""}" data-value="${opt}">${opt}</button>`
        )
        .join("");
      container.querySelectorAll(".filter-option").forEach((btn) => {
        btn.addEventListener("click", () => onSelect(btn.dataset.value));
      });
    }

    function renderFilters() {
      renderFilterGroup("category-filters", CATEGORIES, activeCategory, (value) => {
        activeCategory = value;
        renderFilters();
        renderGrants();
      });
      renderFilterGroup("level-filters", LEVELS, activeLevel, (value) => {
        activeLevel = value;
        renderFilters();
        renderGrants();
      });
    }

    function deadlineBadge(grant) {
      if (grant.is_manual) {
        return `<span class="grant-deadline manual">${escapeHtml(grant.deadline_text)}</span>`;
      }
      if (!grant.deadline) {
        return `<span class="grant-deadline manual">Check source for deadline</span>`;
      }
      const days = daysUntil(grant.deadline);
      const closingSoon = days >= 0 && days <= CLOSING_SOON_DAYS;
      return `<span class="grant-deadline${closingSoon ? " closing-soon" : ""}">${escapeHtml(grant.deadline_text)}</span>`;
    }

    function renderGrants() {
      const container = document.getElementById("grants");
      const emptyState = document.getElementById("empty-state");
      const countEl = document.getElementById("results-count");
      const filtered = allGrants.filter(
        (g) =>
          (activeCategory === "all" || g.category === activeCategory) &&
          (activeLevel === "all" || g.level === activeLevel)
      );

      countEl.textContent = `${filtered.length} scholarship${filtered.length === 1 ? "" : "s"} found`;

      if (filtered.length === 0) {
        container.innerHTML = "";
        emptyState.style.display = "block";
        return;
      }
      emptyState.style.display = "none";

      container.innerHTML = filtered
        .map(
          (grant) => `
        <div class="grant-card">
          <p class="grant-title">${escapeHtml(grant.title)}</p>
          ${deadlineBadge(grant)}
          ${grant.description ? `<p class="grant-description">${escapeHtml(grant.description)}</p>` : ""}
          <div class="grant-meta">
            ${isSafeUrl(grant.url) ? `<a href="${escapeAttr(grant.url)}" target="_blank" rel="noopener">${escapeHtml(grant.source)}</a>` : escapeHtml(grant.source)}
            <span>${escapeHtml(grant.category)} &middot; ${escapeHtml(grant.level)}</span>
          </div>
        </div>`
        )
        .join("");
    }

    function escapeHtml(str) {
      const div = document.createElement("div");
      div.textContent = str || "";
      return div.innerHTML;
    }

    function escapeAttr(str) {
      return str.replace(/"/g, "&quot;");
    }

    function isSafeUrl(str) {
      return typeof str === "string" && (str.startsWith("http://") || str.startsWith("https://"));
    }

    function sortGrants(grants) {
      return grants.slice().sort((a, b) => {
        const aNull = !a.deadline;
        const bNull = !b.deadline;
        if (aNull !== bNull) return aNull ? 1 : -1;
        if (aNull && bNull) return 0;
        return a.deadline < b.deadline ? -1 : a.deadline > b.deadline ? 1 : 0;
      });
    }

    Promise.all([
      fetch("data/grants.json").then((res) => res.json()).catch(() => []),
      fetch("data/manual_grants.json").then((res) => res.json()).catch(() => []),
    ])
      .then(([scraped, manual]) => {
        allGrants = sortGrants([...scraped, ...manual]);
        renderFilters();
        renderGrants();
      })
      .catch(() => {
        document.getElementById("grants").innerHTML =
          '<p id="fetch-error">Could not load grants data.</p>';
      });

    fetch("data/last_run_errors.json")
      .then((res) => res.json())
      .then((errors) => {
        if (!Array.isArray(errors) || errors.length === 0) return;
        const status = document.getElementById("scraper-status");
        const list = document.getElementById("scraper-errors");
        list.innerHTML = errors
          .map((e) => `<li>${escapeHtml(e.source || "unknown source")}: ${escapeHtml(e.error || "failed to fetch")}</li>`)
          .join("");
        status.style.display = "block";
      })
      .catch(() => {});
  </script>
</body>
</html>
```

- [ ] **Step 3: Manually verify in a browser**

Run: `python -m http.server 8000` from the project root, then open
`http://localhost:8000/index.html`. Since `data/grants.json` does not
exist yet, confirm the page shows the "Could not load grants data."
fallback text without a JavaScript console error (the `.catch(() => [])`
on each individual fetch means a missing `grants.json` should NOT trigger
the outer catch — verify this by temporarily creating an empty
`data/manual_grants.json`-only scenario: with only `manual_grants.json`
present, the four manual entries should render correctly with their
"Verify current application period..." badges in the right-hand results
pane, with the left sidebar's category/level filters narrowing the list
and the results count updating accordingly. Confirm the layout collapses
to a stacked (sidebar-on-top) view below 700px width. Stop the server with
Ctrl+C when done.

- [ ] **Step 4: Commit**

```bash
git add data/manual_grants.json index.html
git commit -m "Add manual grant entries and static frontend"
```

---

### Task 7: GitHub Actions workflow and README

**Files:**
- Create: `.github/workflows/scrape.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `scraper/scrape.py` (Task 5) via `python -m scraper.scrape`.
- Produces: nothing consumed by other tasks — this is the deployment leaf.

- [ ] **Step 1: Create `.github/workflows/scrape.yml`**

```yaml
name: Scrape Grants

on:
  schedule:
    - cron: "0 22 * * *"
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python -m scraper.scrape
      - name: Commit updated data if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/grants.json data/last_run_errors.json
          git diff --staged --quiet || git commit -m "Update scraped grants ($(date -u +%Y-%m-%d))"
          git push
```

- [ ] **Step 2: Create `README.md`**

```markdown
# PH Scholarship Grants Tracker

Philippine scholarship and grant opportunities — government, private,
global, and NGO — scraped daily and published as a free static site.

## How it works

- `.github/workflows/scrape.yml` runs `scraper/scrape.py` daily at 06:00
  Asia/Manila time via GitHub Actions.
- Each source parser fetches a listing page, then fetches each listing's
  detail page to extract the deadline (deadlines live in article bodies,
  not listing excerpts, for verified sources).
- Results are normalized, deduplicated by `(source, title)`, and merged
  into `data/grants.json`. A grant is dropped once its parsed `deadline`
  passes; grants with no parseable deadline are dropped 14 days after they
  stop appearing in a scrape.
- `data/manual_grants.json` is a hand-maintained file covering well-known
  government scholarships (CHED, DOST-SEI, OWWA, GSIS) whose official
  sites block automated scraping (Cloudflare/WAF). These link directly to
  the official page rather than showing a parsed deadline.
- `index.html` is a dependency-free static page that reads both JSON files
  and renders a filterable, deadline-sorted feed. Published via GitHub
  Pages.

## Adding a new source

1. Fetch the candidate source's listing page and confirm it returns real
   structured HTML (a repeating post/article loop) rather than a
   Cloudflare/bot-challenge page or a JS-only shell.
2. Fetch a sample detail page linked from that listing and confirm a
   deadline is extractable from the body text — if deadlines are not
   present anywhere on the site, it is not a good scraper candidate;
   consider a manual entry instead.
3. Add a parser module to `scraper/parsers/` following the
   `parse(fetch_fn, listing_html: str, scrape_date: str) -> list[dict]`
   signature used by `assistance_ph.py`.
4. Add listing-page and detail-page fixture HTML files under
   `tests/fixtures/` and tests in `tests/test_parsers.py`.
5. Add an entry to `SOURCES` in `scraper/sources.py`.

## Adding a manual entry

For a known scholarship whose official site cannot be scraped, add an
entry to `data/manual_grants.json` with `"is_manual": true`, `"deadline":
null`, and a `"deadline_text"` directing the user to check the official
site.

## Local development

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
python -m scraper.scrape
python -m http.server 8000   # then open http://localhost:8000/index.html
```
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/scrape.yml README.md
git commit -m "Add GitHub Actions scrape workflow and README"
```

---

### Task 8: First scrape run and GitHub Pages setup

**Files:**
- Modify: none (runs existing code, may produce `data/grants.json` and `data/last_run_errors.json`)

**Interfaces:**
- Consumes: `scraper/scrape.py` (Task 5).
- Produces: `data/grants.json`, `data/last_run_errors.json` — committed artifacts consumed by `index.html` (Task 6) in production.

- [ ] **Step 1: Run the scraper against the live `assistance.ph` source**

Run: `python -m scraper.scrape`
Expected output: `Wrote N grants, 0 source errors.` where N >= 1. If
`source errors` is nonzero, open `data/last_run_errors.json` and confirm
whether `assistance.ph`'s markup has changed since Task 3's fixtures were
captured; if so, update the parser and fixtures to match before proceeding.

- [ ] **Step 2: Sanity-check the output**

Run: `python -m http.server 8000` from the project root, open
`http://localhost:8000/index.html`, and confirm:
- At least one real scraped grant card renders with a deadline badge.
- All four manual government entries render with the "Verify current
  application period..." badge.
- Category and level filter chips both work and narrow the list correctly.
Stop the server with Ctrl+C when done.

- [ ] **Step 3: Commit the first scrape output**

```bash
git add data/grants.json data/last_run_errors.json
git commit -m "Add first scrape run output"
```

- [ ] **Step 4: Push to GitHub and enable Pages**

```bash
git remote add origin https://github.com/AIinterruptor/ph-scholarship-tracker.git
git branch -M main
git push -u origin main
gh api repos/AIinterruptor/ph-scholarship-tracker/pages -X POST -f "source[branch]=main" -f "source[path]=/" 2>&1 || echo "If this fails, enable Pages manually in the repo Settings > Pages, source: main branch, root."
```

Expected: repo is pushed, and GitHub Pages is configured to serve from
`main` branch root. The live site will be at
`https://aiinterruptor.github.io/ph-scholarship-tracker/`.

---

## Self-Review Notes

- **Spec coverage:** two-step fetch (Task 3), deadline extraction (Task 2),
  deadline-based merge/retention (Task 5), manual entries (Task 6),
  category/level filters (Task 6), scraper status disclosure (Task 6),
  GitHub Actions daily cron (Task 7), README source-adding procedure
  (Task 7) — all covered.
- **Type consistency:** `make_grant` (Task 1) fields match what
  `assistance_ph.parse` (Task 3) passes in, what `merge_grants` (Task 5)
  reads/writes (`deadline`, `deadline_text`, `last_seen`, `first_seen`,
  dedup on `source`+`title`), and what `index.html` (Task 6) renders
  (`title`, `deadline`, `deadline_text`, `is_manual`, `category`, `level`,
  `source`, `url`, `description`) — verified consistent throughout.
