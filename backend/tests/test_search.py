from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.data import load_listings
from app.models import Listing
from app.search import (
    MAX_PAGE_SIZE,
    InvalidSearchError,
    ScoredListing,
    SearchParams,
    budget_score,
    matches_keyword,
    rank_key,
    recency_score,
    relevance_score,
    search,
)

TODAY = date(2026, 9, 30)
SAMPLE = load_listings()

BASE = Listing(
    id="X1",
    source="MLS_A",
    address="1 Test St",
    city="Springfield",
    state="VA",
    zip="22150",
    price=500_000,
    bedrooms=3,
    bathrooms=2.0,
    sqft=1500,
    latitude=0.0,
    longitude=0.0,
    listed_date=TODAY,
    status="active",
    description="Plain house.",
)


def make(id: str, **changes) -> Listing:
    return replace(BASE, id=id, **changes)


def numbered(count: int) -> list[Listing]:
    """L01 is newest, L02 a day older, ... so they always rank L01, L02, ..."""
    return [make(f"L{i:02}", listed_date=TODAY - timedelta(days=i)) for i in range(1, count + 1)]


def ids(result) -> list[str]:
    return [item.listing.id for item in result.results]


# ---------- filters ----------

def test_no_filters_returns_every_listing():
    assert search(SAMPLE, SearchParams(page_size=50), TODAY).total_results == 12


def test_price_range_is_inclusive():
    listings = [
        make("low", price=399_999),
        make("min", price=400_000),
        make("max", price=500_000),
        make("high", price=500_001),
    ]
    result = search(listings, SearchParams(min_price=400_000, max_price=500_000), TODAY)
    assert sorted(ids(result)) == ["max", "min"]


def test_min_price_equal_to_max_price_is_allowed():
    result = search(SAMPLE, SearchParams(min_price=450_000, max_price=450_000), TODAY)
    assert ids(result) == ["A1"]


def test_min_bedrooms_is_inclusive():
    listings = [make("two", bedrooms=2), make("three", bedrooms=3), make("four", bedrooms=4)]
    assert sorted(ids(search(listings, SearchParams(min_bedrooms=3), TODAY))) == ["four", "three"]


def test_city_ignores_case_and_extra_spaces():
    result = search(SAMPLE, SearchParams(city="  reston "), TODAY)
    assert result.total_results == 2
    assert {item.listing.city for item in result.results} == {"Reston"}


def test_blank_city_means_any_city():
    assert search(SAMPLE, SearchParams(city="   ", page_size=50), TODAY).total_results == 12


def test_filters_combine():
    params = SearchParams(city="Springfield", min_bedrooms=3, keyword="kitchen")
    assert sorted(ids(search(SAMPLE, params, TODAY))) == ["A2", "B8"]


@pytest.mark.parametrize(
    "description, keyword, expected",
    [
        ("Pets allowed.", "pet", True),  # start of a word
        ("Pets allowed.", "PETS", True),  # case-insensitive
        ("Pets allowed.", "pets allowed", True),
        ("Pets allowed.", "pets pool", False),  # every word must match
        ("New carpet.", "pet", False),  # not inside another word
        ("Anything.", "", True),
        ("Anything.", "   ", True),
        ("Anything.", None, True),
    ],
)
def test_keyword_matching(description, keyword, expected):
    assert matches_keyword(description, keyword) is expected


def test_keyword_known_limit_does_not_understand_no():
    # Documented in the README: "pets" also matches "no pets".
    assert matches_keyword("Cozy home, no pets.", "pets") is True


# ---------- no matches ----------

def test_known_city_with_no_matches_is_empty_not_an_error():
    result = search(SAMPLE, SearchParams(city="Fairfax", min_bedrooms=5), TODAY)
    assert (result.results, result.total_results, result.total_pages) == ([], 0, 0)


def test_keyword_with_no_matches_is_empty():
    assert search(SAMPLE, SearchParams(keyword="helicopter"), TODAY).total_results == 0


# ---------- scoring ----------

def test_budget_score_is_full_at_target_and_never_negative():
    assert budget_score(500_000, 500_000) == 1.0
    assert budget_score(450_000, 500_000) == pytest.approx(0.9)
    assert budget_score(550_000, 500_000) == pytest.approx(0.9)  # above and below count the same
    assert budget_score(1_500_000, 500_000) == 0.0


def test_recency_score_halves_every_30_days():
    assert recency_score(TODAY, TODAY) == 1.0
    assert recency_score(TODAY - timedelta(days=30), TODAY) == pytest.approx(0.5)
    assert recency_score(TODAY - timedelta(days=60), TODAY) == pytest.approx(0.25)


def test_future_listing_date_counts_as_today():
    assert recency_score(TODAY + timedelta(days=5), TODAY) == 1.0


def test_score_runs_from_0_to_100():
    best = make("best", price=500_000, listed_date=TODAY)
    worst = make("worst", price=5_000_000, listed_date=TODAY - timedelta(days=3650))
    assert relevance_score(best, 500_000, TODAY) == 100.0
    assert relevance_score(worst, 500_000, TODAY) == 0.0


def test_closest_to_budget_ranks_first():
    listings = [make("far", price=700_000), make("exact", price=500_000), make("near", price=520_000)]
    result = search(listings, SearchParams(target_budget=500_000), TODAY)
    assert ids(result) == ["exact", "near", "far"]


def test_without_budget_newest_ranks_first():
    listings = [
        make("old", listed_date=TODAY - timedelta(days=40)),
        make("new", listed_date=TODAY - timedelta(days=1)),
    ]
    assert ids(search(listings, SearchParams(), TODAY)) == ["new", "old"]


def test_much_newer_listing_can_beat_a_slightly_closer_price():
    fresh = make("fresh", price=510_000, listed_date=TODAY)  # 98.6
    stale = make("stale", price=500_000, listed_date=TODAY - timedelta(days=90))  # 73.8
    result = search([stale, fresh], SearchParams(target_budget=500_000), TODAY)
    assert ids(result) == ["fresh", "stale"]


# ---------- tied scores ----------

def test_tied_scores_break_by_newer_then_cheaper_then_source_and_id():
    tied = [
        ScoredListing(make("A9", price=400_000, listed_date=TODAY - timedelta(days=1)), 80.0),
        ScoredListing(make("A2", price=450_000), 80.0),
        ScoredListing(make("A1", price=450_000), 80.0),
        ScoredListing(make("B1", price=450_000, source="MLS_B"), 80.0),
        ScoredListing(make("A3", price=400_000), 80.0),
    ]
    ranked = sorted(tied, key=rank_key)
    assert [item.listing.id for item in ranked] == ["A3", "A1", "A2", "B1", "A9"]


def test_same_search_gives_same_order_whatever_the_input_order():
    listings = [make("A2"), make("A1"), make("A3")]  # identical apart from id, so scores tie
    params = SearchParams(target_budget=500_000)
    forward = ids(search(listings, params, TODAY))
    backward = ids(search(list(reversed(listings)), params, TODAY))
    assert forward == backward == ["A1", "A2", "A3"]


# ---------- invalid input ----------

@pytest.mark.parametrize(
    "params, field",
    [
        (SearchParams(min_price=500_000, max_price=400_000), "minPrice"),
        (SearchParams(min_price=-1), "minPrice"),
        (SearchParams(max_price=-1), "maxPrice"),
        (SearchParams(min_price=float("nan")), "minPrice"),
        (SearchParams(max_price=float("inf")), "maxPrice"),
        (SearchParams(min_bedrooms=-1), "minBedrooms"),
        (SearchParams(target_budget=0), "targetBudget"),
        (SearchParams(target_budget=-100), "targetBudget"),
        (SearchParams(page=0), "page"),
        (SearchParams(page=-1), "page"),
        (SearchParams(page_size=0), "pageSize"),
        (SearchParams(page_size=-5), "pageSize"),
        (SearchParams(page_size=MAX_PAGE_SIZE + 1), "pageSize"),
        (SearchParams(city="Bostn"), "city"),
    ],
)
def test_invalid_input_is_rejected_with_the_field_name(params, field):
    with pytest.raises(InvalidSearchError) as error:
        search(SAMPLE, params, TODAY)
    assert error.value.field == field


def test_unknown_city_error_lists_known_cities():
    with pytest.raises(
        InvalidSearchError,
        match="Known cities: Chantilly, Fairfax, Manassas, Reston, Springfield, Vienna",
    ):
        search(SAMPLE, SearchParams(city="Bostn"), TODAY)


# ---------- pagination ----------

def test_first_page():
    result = search(numbered(7), SearchParams(page=1, page_size=3), TODAY)
    assert ids(result) == ["L01", "L02", "L03"]
    assert (result.total_results, result.total_pages) == (7, 3)


def test_last_page_can_be_partly_full():
    result = search(numbered(7), SearchParams(page=3, page_size=3), TODAY)
    assert ids(result) == ["L07"]


def test_exactly_full_last_page_has_no_extra_empty_page():
    result = search(numbered(6), SearchParams(page=2, page_size=3), TODAY)
    assert ids(result) == ["L04", "L05", "L06"]
    assert result.total_pages == 2
    with pytest.raises(InvalidSearchError) as error:
        search(numbered(6), SearchParams(page=3, page_size=3), TODAY)
    assert error.value.field == "page"


def test_page_past_the_end_is_an_error():
    with pytest.raises(InvalidSearchError, match="only 3 page"):
        search(numbered(7), SearchParams(page=4, page_size=3), TODAY)


def test_page_size_of_one_and_the_maximum_are_allowed():
    assert search(numbered(3), SearchParams(page_size=1), TODAY).total_pages == 3
    assert search(numbered(3), SearchParams(page_size=MAX_PAGE_SIZE), TODAY).total_pages == 1


def test_pages_do_not_overlap_and_cover_everything():
    listings = numbered(7)
    seen = []
    for page in (1, 2, 3):
        seen += ids(search(listings, SearchParams(page=page, page_size=3), TODAY))
    assert seen == [f"L{i:02}" for i in range(1, 8)]
