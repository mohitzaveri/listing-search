# Listing Search

A small full-stack search over property listings from several MLS feeds.

- **Backend:** Python 3.12+ / FastAPI. Listings are loaded from `backend/data/sample_listings.json` into memory at startup.
- **Frontend:** React + TypeScript (Vite). A minimal page that calls the API and shows ranked, paginated results. Light and dark mode, works on phones.

## Run it

You need Python 3.12+ and Node 22+.

**Terminal 1: API** on http://localhost:8000 (interactive docs at `/docs`). Use either option.

With plain `pip`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --port 8000
```

**Terminal 2: UI** on http://localhost:5173 (proxies `/api` to the backend):

```bash
cd frontend
npm install
npm run dev
```

To try the production build instead of the dev server: `npm run build && npm run preview` (UI on http://localhost:4173).

**Tests** (from `backend/`): `pytest` with the pip setup, or `uv run pytest` with uv.

`requirements.txt` has the same pinned versions as `uv.lock`. It was generated with `uv export --format requirements-txt --no-hashes --no-emit-project -o requirements.txt`.

## API

`GET /api/listings/search`

| Param          | Type   | Meaning                                                      |
| -------------- | ------ | ------------------------------------------------------------ |
| `minPrice`     | number | Price ≥ this                                                 |
| `maxPrice`     | number | Price ≤ this                                                 |
| `minBedrooms`  | int    | Bedrooms ≥ this                                              |
| `city`         | string | Exact city, ignoring case and extra spaces                   |
| `keyword`      | string | Every word must start a word in the description              |
| `targetBudget` | number | Used for ranking (see Scoring)                               |
| `page`         | int    | 1-based, default 1                                           |
| `pageSize`     | int    | 1–50, default 10                                             |

All params are optional. A successful response looks like this:

```json
{
  "results": [{ "id": "A1", "source": "MLS_A", "address": "123 Main St, Apt 4B", "price": 450000, "bedrooms": 2, "score": 84.3, "...": "..." }],
  "page": 1,
  "pageSize": 10,
  "totalResults": 12,
  "totalPages": 2
}
```

Bad input returns **HTTP 400** with the field to blame, so the UI can highlight it:

```json
{ "error": { "field": "minPrice", "message": "minPrice cannot be greater than maxPrice." } }
```

## Scoring

Each result gets a **0–100** relevance score:

```
score = 100 × (0.7 × budgetScore + 0.3 × recencyScore)
budgetScore  = max(0, 1 − |price − targetBudget| / targetBudget)
recencyScore = 0.5 ^ (daysSinceListed / 30)
```

- **Budget (70%).** The score is 1.0 at exactly the budget and falls in a straight line to 0 at 100% away. Above and below the budget count the same. Budget gets the bigger weight because price fit matters most to a buyer.
- **Recency (30%).** A listing loses half its freshness every 30 days, so new listings get a boost without old ones dropping to zero overnight. A future `listedDate` counts as today.
- **No `targetBudget` given:** the score is recency only (`100 × recencyScore`), so the newest listings come first.
- **Ties:** results are sorted by score, then newer `listedDate`, then lower price, then `source`, then `id`. The same search always gives the same order.

Worked example: with a budget of $450,000 and today = 2026-09-30, A1 is priced at $450,000 and was listed 32 days ago:
`0.7 × 1.0 + 0.3 × 0.5^(32/30) = 0.843` → **84.3**.

Why this formula: it's simple, every part is easy to explain, and the two knobs (`BUDGET_WEIGHT`, `RECENCY_HALF_LIFE_DAYS` in `app/search.py`) are easy to tune.

## Input handling

| Input                                                   | Result                                                       |
| ------------------------------------------------------- | ------------------------------------------------------------ |
| `minPrice > maxPrice`                                   | 400, field `minPrice`                                        |
| Negative, `NaN` or `Infinity` price / bedrooms          | 400                                                          |
| `targetBudget ≤ 0`                                      | 400                                                          |
| `page < 1`, or `page` past the last page                | 400, says how many pages exist                               |
| `pageSize < 1` or `> 50`                                | 400                                                          |
| Text in a number field (`minPrice=abc`)                 | 400 (same error shape)                                       |
| Unknown or misspelled parameter (`minprice`)            | 400, suggests the right name ("Did you mean 'minPrice'?")    |
| City not in the data (`Bostn`)                          | 400, lists the known cities: most likely a typo              |
| Known city, but the other filters remove everything     | 200 with empty `results`: a real "no matches"                |
| Blank `city` / `keyword`                                | Ignored ("any")                                              |

## Project layout

```
backend/
  app/search.py     validate → filter → score → sort → paginate (no web code, fully unit tested)
  app/main.py       FastAPI endpoint + turns errors into 400 responses
  app/models.py     Listing dataclass
  app/data.py       loads the JSON feed
  tests/            test_search.py (core logic), test_api.py (HTTP layer)
frontend/
  src/App.tsx       filter form + search state (which filters, which page, loading, error)
  src/Results.tsx   results table, pagination, loading skeleton, empty state
  src/api.ts        fetch + small cache; turns API errors into ApiError
```

## Trade-offs

- **In-memory list, no database.** This is fine for a sample of 12 listings and keeps the logic easy to test. With real data volumes, the filters would move into SQL or a search index and scoring would run on the filtered rows.
- **Scoring runs on all matches before paging,** so the best result is always on page 1. That costs O(n log n) per request, which is fine at this size.
- **The server is the only validator.** The UI doesn't repeat the checks; it shows the API's message and highlights the field. One source of truth, at the cost of one round trip.
- **"Today" is injected** (`get_today` dependency), so tests are stable and don't change with the calendar.
- **Fast frontend, few moving parts.** There is no UI library, no CSS framework and no web fonts; the whole page is ~73 KB gzipped, mostly React itself. Each distinct query is cached in memory (max 50) and the next page is prefetched, so Next/Previous are usually instant. Old results stay on screen, dimmed, while a new page loads, so nothing jumps. The trade-off is that the cache assumes listings don't change while the page is open. With live feeds, it would need a short expiry.

## Known issues and next steps

- **Duplicate listings across feeds.** For example, A1 / B7 are the same home ("123 Main St, Apt 4B" vs "123 Main Street, Unit 4B"), and 4 such pairs exist in the sample. All pairs share exact latitude/longitude. A de-duplication step would slot into `search()` before filtering.
- **Status is not filtered.** Pending/sold listings (e.g. A7 is `pending`) are shown, with their status in the table. A `status` filter defaulting to `active` would be a small addition.
- **Keyword search has no negation.** `pets` also matches "No pets". Fixing that needs real text understanding, which is out of scope here.
- **Address / ZIP inconsistencies between feeds** (e.g. A2 22150 vs B8 22151) are shown as-is.
