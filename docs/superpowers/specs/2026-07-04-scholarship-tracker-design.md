# PH Scholarship Grants Tracker — Design

## Purpose

A free, zero-infrastructure directory of Philippine scholarship and grant
opportunities — government, private, global, and NGO — for undergrad-bound
students (high school through current undergrad). Mirrors the architecture
of the existing `ph-discounts-tracker` project.

## Architecture

- A Python scraper (`scraper/scrape.py`) runs daily via GitHub Actions cron.
- Each source has a parser under `scraper/parsers/` that extracts structured
  listings from that source's HTML.
- Results are normalized, deduplicated, merged with existing data, and
  written to `data/grants.json` (plus `data/last_run_errors.json` for any
  source that failed to fetch/parse that run).
- The workflow commits the updated JSON back to the repo.
- `index.html` is a dependency-free static page that fetches
  `data/grants.json` directly and renders a filterable feed. Published via
  GitHub Pages.
- No backend server, no database, no build step, no user auth, no
  crowdsourcing/submissions in v1.

## Data model

Each grant record:

```json
{
  "title": "DOST-SEI Undergraduate Scholarship",
  "description": "Cleaned plain-text summary of the program.",
  "deadline": "2026-08-30",
  "deadline_text": "Apply on or before August 30, 2026",
  "url": "https://source-page-url",
  "category": "government",
  "level": "undergrad",
  "source": "DOST-SEI",
  "first_seen": "2026-07-04",
  "last_seen": "2026-07-04"
}
```

Field notes:

- `deadline` — nullable, ISO `YYYY-MM-DD`. Best-effort regex/date parse per
  parser. Drives archival. Null when a source gives no clean date (e.g.
  "until slots last", no date at all).
- `deadline_text` — raw deadline phrasing as it appears on the source page.
  Always populated when any deadline-like text exists; shown verbatim in the
  UI regardless of whether `deadline` parsed successfully.
- `category` — one of `government`, `private`, `global`, `ngo`. A category
  may legitimately have zero sources at launch if no scrapeable source is
  found for it (see Sourcing below).
- `level` — one of `undergrad`, `graduate`, `professional`. v1 audience is
  primarily undergrad-bound; graduate/professional listings are included
  opportunistically if a source naturally surfaces them, not specifically
  hunted for.

## Merge and retention logic

Replaces the discount tracker's flat "drop if unseen 14 days" rule, since
scholarships have real deadlines rather than a continuous promo lifecycle.

Dedup key: `(source, title)` — not `(source, title, discount_text)` as in
the discount tracker, because a scholarship recurs annually under the same
title with a new deadline each cycle.

On each merge:

1. For a freshly-scraped listing matching an existing dedup key: update
   `last_seen`, `deadline`, and `deadline_text` from the fresh scrape (so an
   annually-reopening scholarship flips back to "open" with the new date).
2. For a freshly-scraped listing with a new dedup key: add it as-is.
3. Retention (which existing listings survive into the merged output):
   - If `deadline` is set: keep while `deadline >= scrape_date`. Drop once
     the deadline has passed.
   - If `deadline` is null: keep while unseen for ≤ 14 days from
     `last_seen` (same rule as the discount tracker), to avoid indefinitely
     retaining listings that can't be date-checked.
4. Sort output ascending by `deadline`, with null-deadline listings sorted
   last (by `first_seen` descending among themselves). Soonest-closing
   first is the core value-add for a scholarship hunter, versus the
   discount tracker's newest-first ordering.

## Frontend (`index.html`)

Same dependency-free static page pattern and dark/light theming as the
discount tracker. Differences:

- Filter chips: category (`government` / `private` / `global` / `ngo`) and
  level (`undergrad` / `graduate` / `professional`).
- The discount tracker's `.deal-discount` badge becomes a deadline badge:
  - Shows `deadline_text` verbatim.
  - Highlighted (e.g. distinct color) as "Closing Soon" if `deadline` is
    within 14 days of today.
  - Shows "Check source for deadline" styling if `deadline` is null.
- List order follows the sort from the merge step (soonest deadline first)
  rather than being re-sorted client-side.
- Same `last_run_errors.json` scraper-status disclosure pattern.

## Sourcing

Scholarship sites are less scraper-friendly than the discount tracker's
retail promo pages — many post as PDFs, Facebook-only announcements, or are
behind bot-protection. Confirmed during design:

- CHED and DOST-SEI main scholarship pages are behind Cloudflare
  bot-challenges (403 "Just a moment..." to a plain GET) — **not
  scrapeable** by a GitHub Actions runner without a browser-rendering layer,
  which is out of scope for v1. These are not included as v1 sources.
- SM Foundation and UniFAST returned 200 but showed thin/JS-rendered content
  on a quick check — not yet confirmed scrapeable.

Given this, v1 does **not** hardcode a final source list into this spec.
Instead:

- The implementation phase performs a scrapeability check (fetch + confirm
  real structured listing HTML, no Cloudflare/JS wall) on each candidate
  source before writing a parser for it — same as the "Adding a new source"
  workflow the discount tracker documents in its README, just front-loaded.
- Target: at least a small initial set (roughly 2-5) of confirmed-scrapeable
  sources across any mix of the four categories. No per-category minimum is
  required for v1 — a category may start with zero sources if nothing
  scrapeable is found for it, to be revisited later (manual curation or a
  browser-rendering fetch layer, both out of scope for v1).
- Sources that are clearly real and valuable but not scrapeable (PDF-only,
  Facebook-only, Cloudflare-gated) are noted in the README as "manual/v2
  candidates" rather than silently dropped from consideration.

## Testing

Mirrors the discount tracker's test suite:

- `tests/test_merge.py` — adapted for deadline-based retention: new listing
  added, re-seen listing updates `deadline`/`last_seen`, past-deadline
  listing dropped, null-deadline listing follows the 14-day fallback,
  output sort order.
- `tests/test_parsers.py` — one fixture HTML file and test per source
  parser.
- `tests/test_models.py` — record normalization (`make_grant`-equivalent
  helper).

## Out of scope for v1

- User accounts, submissions, or crowdsourcing.
- Browser-rendering/headless-browser fetching for JS-heavy or
  Cloudflare-protected sources.
- Email/notification alerts for closing deadlines.
- Non-PH-focused or purely graduate/professional-only scope (see `level`
  field — undergrad is the primary audience, not the exclusive one).
