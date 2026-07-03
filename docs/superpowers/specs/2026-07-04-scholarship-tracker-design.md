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
- **Two-step fetch per scraped source** (a delta from the discount
  tracker's single-fetch model): a parser first fetches the source's
  listing/index page to collect candidate titles and detail-page URLs, then
  fetches each detail page to extract the description and deadline. This is
  required because, on verified sources (e.g. `assistance.ph`), the listing
  excerpt is truncated/empty and the deadline only appears in the full
  article body. Listing-page fetch failures are a source-level error;
  individual detail-page fetch failures are skipped per-listing (logged,
  not fatal to the whole source).
- Results are normalized, deduplicated, merged with existing data, and
  written to `data/grants.json` (plus `data/last_run_errors.json` for any
  source or detail-page fetch that failed that run).
- The workflow commits the updated JSON back to the repo.
- `index.html` is a dependency-free static page that fetches
  `data/grants.json` directly and renders a filterable feed. Published via
  GitHub Pages.
- No backend server, no database, no build step, no user auth, no
  crowdsourcing/submissions in v1.
- **Static manual-check entries** for known major sources that cannot be
  scraped at all (confirmed: CHED, DOST-SEI, OWWA, GSIS — all behind
  Cloudflare/WAF bot-protection that returns a challenge or rejection page
  to a plain HTTP GET). These are hand-maintained records with no
  `deadline`/`description` scraped — see Sourcing below.

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
  "is_manual": false,
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
  UI regardless of whether `deadline` parsed successfully. For manual-check
  entries (see below), this is a fixed string directing the user to check
  the source site.
- `category` — one of `government`, `private`, `global`, `ngo`. A category
  may legitimately have zero *scraped* sources at launch if no scrapeable
  source is found for it (see Sourcing below); `government` in particular
  is expected to be covered mainly by manual-check entries.
- `level` — one of `undergrad`, `graduate`, `professional`. v1 audience is
  primarily undergrad-bound; graduate/professional listings are included
  opportunistically if a source naturally surfaces them, not specifically
  hunted for.
- `is_manual` — `true` for hand-maintained entries representing a known
  scholarship whose official source cannot be scraped (Cloudflare/WAF
  blocked). `false` (or omitted) for scraper-derived entries. Manual
  entries are excluded from the scraper's merge/retention pass entirely —
  they are static data, edited by hand, never auto-dropped by deadline or
  staleness.

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

Manual entries (`is_manual: true`) are not produced by `scrape.py` and are
never touched by the merge step above. They live in a separate hand-edited
file (`data/manual_grants.json`) and are concatenated with the
scraper-merged results only at publish time (see Sourcing), then included
together in the same ascending-by-`deadline` sort for display.

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
- Manual entries (`is_manual: true`) render as a normal card but with a
  distinct badge/label (e.g. "Verify on official site") instead of a
  deadline badge, and their card link points at the official source's
  scholarship page rather than a specific post.
- List order follows the sort from the merge step (soonest deadline first)
  rather than being re-sorted client-side.
- Same `last_run_errors.json` scraper-status disclosure pattern.

## Sourcing

Scholarship sites are less scraper-friendly than the discount tracker's
retail promo pages — many post as PDFs, Facebook-only announcements, or are
behind bot-protection. Confirmed during design:

- CHED, DOST-SEI, OWWA, and GSIS official scholarship pages are all behind
  Cloudflare or WAF bot-protection (403 "Just a moment..." challenge, or an
  outright "Request Rejected" response) to a plain GET — **not scrapeable**
  by a GitHub Actions runner without a browser-rendering layer, which is
  out of scope for v1. These well-known programs are instead represented as
  hand-maintained **manual-check entries** (`is_manual: true`) in
  `data/manual_grants.json`, each linking directly to the program's
  official page so the user can verify current status/deadline themselves.
- `assistance.ph` is confirmed scrapeable: a real WordPress site with a
  structured homepage `<article>` post loop (`h2.entry-title` + permalink),
  and individual posts (e.g. `/ched-ease-scholarship/`) contain real
  deadline text in the body (e.g. "The application window closes on July
  31, 2026"). This is the v1 reference source and reference parser.
- SM Foundation and UniFAST returned 200 but showed thin/JS-rendered content
  on a quick check — not yet confirmed scrapeable; left as v2 candidates.

v1 does **not** hardcode a final scraped-source list beyond the one
confirmed reference source. Instead:

- `scraper/sources.py` ships with `assistance.ph` as a working, tested
  source using the two-step (listing + detail page) fetch pattern.
- Additional sources are added by the same procedure the discount tracker
  documents in its README ("Adding a new source"), updated for the
  two-step fetch: a scrapeability check (fetch listing page, confirm a real
  structured post loop; fetch a sample detail page, confirm the deadline is
  extractable) before writing a parser.
- No per-category minimum is required for v1 — a category may be covered
  entirely by manual entries (as `government` is) or have zero entries at
  launch.
- Sources that are clearly real and valuable but not scrapeable (PDF-only,
  Facebook-only, Cloudflare/WAF-gated) are noted in the README as
  "manual/v2 candidates," following the same pattern as the four
  confirmed-blocked government sources.

## Testing

Mirrors the discount tracker's test suite:

- `tests/test_merge.py` — adapted for deadline-based retention: new listing
  added, re-seen listing updates `deadline`/`last_seen`, past-deadline
  listing dropped, null-deadline listing follows the 14-day fallback,
  output sort order. Includes a case where deadline text fails to parse
  cleanly (e.g. ambiguous/partial date) and degrades to `deadline: null` +
  a populated `deadline_text`, rather than producing a wrong date.
- `tests/test_parsers.py` — fixture-based: one listing-page fixture and one
  or more detail-page fixtures per source parser, covering the two-step
  fetch.
- `tests/test_models.py` — record normalization (`make_grant`-equivalent
  helper).
- `tests/test_deadline_parsing.py` — the date-extraction helper in
  isolation, against a table of real deadline phrasings collected from
  verified sources (e.g. "The application window closes on July 31,
  2026") plus edge cases (no date present, relative phrasing like "until
  slots last").

## Out of scope for v1

- User accounts, submissions, or crowdsourcing.
- Browser-rendering/headless-browser fetching for JS-heavy or
  Cloudflare-protected sources.
- Email/notification alerts for closing deadlines.
- Non-PH-focused or purely graduate/professional-only scope (see `level`
  field — undergrad is the primary audience, not the exclusive one).
