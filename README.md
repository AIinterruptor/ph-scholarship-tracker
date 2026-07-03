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
