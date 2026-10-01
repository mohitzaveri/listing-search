"""Core search logic: validate -> filter -> score -> sort -> paginate.

Nothing here knows about HTTP, so each step can be unit tested on its own
and a new step (e.g. de-duplication) can be slotted into `search()`.
"""

import math
import re
from dataclasses import dataclass
from datetime import date

from app.models import Listing

MAX_PAGE_SIZE = 50

# Scoring knobs. See README "Scoring" for the reasoning.
BUDGET_WEIGHT = 0.7
RECENCY_WEIGHT = 0.3
RECENCY_HALF_LIFE_DAYS = 30


class InvalidSearchError(ValueError):
    """Search input we refuse to run. `field` names the input that is wrong."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class SearchParams:
    min_price: float | None = None
    max_price: float | None = None
    min_bedrooms: int | None = None
    city: str | None = None
    keyword: str | None = None
    target_budget: float | None = None
    page: int = 1
    page_size: int = 10


@dataclass(frozen=True)
class ScoredListing:
    listing: Listing
    score: float


@dataclass(frozen=True)
class SearchResult:
    results: list[ScoredListing]
    page: int
    page_size: int
    total_results: int
    total_pages: int


def search(listings: list[Listing], params: SearchParams, today: date) -> SearchResult:
    validate(params, listings)
    matches = [listing for listing in listings if matches_filters(listing, params)]
    scored = [
        ScoredListing(listing, relevance_score(listing, params.target_budget, today))
        for listing in matches
    ]
    ranked = sorted(scored, key=rank_key)
    return paginate(ranked, params.page, params.page_size)


# ---------- validate ----------

def validate(params: SearchParams, listings: list[Listing]) -> None:
    _require_non_negative("minPrice", params.min_price)
    _require_non_negative("maxPrice", params.max_price)
    _require_non_negative("minBedrooms", params.min_bedrooms)

    if params.target_budget is not None and not (
        math.isfinite(params.target_budget) and params.target_budget > 0
    ):
        raise InvalidSearchError("targetBudget", "targetBudget must be greater than 0.")

    if (
        params.min_price is not None
        and params.max_price is not None
        and params.min_price > params.max_price
    ):
        raise InvalidSearchError("minPrice", "minPrice cannot be greater than maxPrice.")

    if params.page < 1:
        raise InvalidSearchError("page", "page must be 1 or more.")

    if not 1 <= params.page_size <= MAX_PAGE_SIZE:
        raise InvalidSearchError("pageSize", f"pageSize must be between 1 and {MAX_PAGE_SIZE}.")

    # A city we have never seen is almost always a typo, so say so instead of
    # returning a silent empty list. A known city that other filters empty out
    # is a normal "no results" answer, not an error.
    wanted_city = normalize_city(params.city)
    if wanted_city and wanted_city not in {normalize_city(listing.city) for listing in listings}:
        known = sorted({listing.city.strip() for listing in listings}, key=str.lower)
        raise InvalidSearchError(
            "city",
            f"No listings in '{params.city.strip()}'. Known cities: {', '.join(known)}.",
        )


def _require_non_negative(field: str, value: float | None) -> None:
    if value is not None and not (math.isfinite(value) and value >= 0):
        raise InvalidSearchError(field, f"{field} must be a number of 0 or more.")


# ---------- filter ----------

def matches_filters(listing: Listing, params: SearchParams) -> bool:
    if params.min_price is not None and listing.price < params.min_price:
        return False
    if params.max_price is not None and listing.price > params.max_price:
        return False
    if params.min_bedrooms is not None and listing.bedrooms < params.min_bedrooms:
        return False
    wanted_city = normalize_city(params.city)
    if wanted_city and normalize_city(listing.city) != wanted_city:
        return False
    return matches_keyword(listing.description, params.keyword)


def normalize_city(city: str | None) -> str:
    """Feeds differ in case and spacing, so compare 'reston ' == 'Reston'."""
    return " ".join((city or "").split()).lower()


_WORD = re.compile(r"[a-z0-9]+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def matches_keyword(description: str, keyword: str | None) -> bool:
    """Every word of the keyword must be the start of some word in the description.

    "pet" matches "Pets allowed" but not "carpet". A blank keyword matches everything.
    Known limit: "pets" also matches "No pets" (no negation handling).
    """
    description_words = _words(description)
    return all(
        any(word.startswith(wanted) for word in description_words)
        for wanted in _words(keyword or "")
    )


# ---------- score ----------

def budget_score(price: float, target_budget: float) -> float:
    """1.0 at exactly the budget, falling in a straight line to 0 at 100% away."""
    return max(0.0, 1 - abs(price - target_budget) / target_budget)


def recency_score(listed_date: date, today: date) -> float:
    """1.0 if listed today, halving every RECENCY_HALF_LIFE_DAYS. Future dates count as today."""
    age_days = max(0, (today - listed_date).days)
    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def relevance_score(listing: Listing, target_budget: float | None, today: date) -> float:
    """0-100. With no budget given, recency is the only signal."""
    recency = recency_score(listing.listed_date, today)
    if target_budget is None:
        return round(100 * recency, 1)
    budget = budget_score(listing.price, target_budget)
    return round(100 * (BUDGET_WEIGHT * budget + RECENCY_WEIGHT * recency), 1)


# ---------- sort ----------

def rank_key(item: ScoredListing) -> tuple:
    """Highest score first. Ties go to the newer listing, then the cheaper one,
    then source/id, so the same search always returns the same order."""
    listing = item.listing
    return (-item.score, -listing.listed_date.toordinal(), listing.price, listing.source, listing.id)


# ---------- paginate ----------

def paginate(ranked: list[ScoredListing], page: int, page_size: int) -> SearchResult:
    total = len(ranked)
    total_pages = math.ceil(total / page_size)
    if total and page > total_pages:
        raise InvalidSearchError(
            "page", f"page {page} does not exist; there are only {total_pages} page(s)."
        )
    start = (page - 1) * page_size
    return SearchResult(
        results=ranked[start : start + page_size],
        page=page,
        page_size=page_size,
        total_results=total,
        total_pages=total_pages,
    )
