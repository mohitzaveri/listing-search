from datetime import date

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.data import load_listings
from app.search import InvalidSearchError, SearchParams, search

app = FastAPI(title="Listing Search API")

LISTINGS = load_listings()


def get_today() -> date:
    """A dependency so tests can pin "today" and get stable scores."""
    return date.today()


def error_response(field: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": {"field": field, "message": message}})


@app.exception_handler(InvalidSearchError)
async def handle_invalid_search(_: Request, exc: InvalidSearchError) -> JSONResponse:
    return error_response(exc.field, exc.message)


@app.exception_handler(RequestValidationError)
async def handle_bad_query_type(_: Request, exc: RequestValidationError) -> JSONResponse:
    # e.g. minPrice=abc. FastAPI's default is a 422 with a nested list;
    # return the same 400 shape as every other input error.
    first = exc.errors()[0]
    field = str(first["loc"][-1])
    return error_response(field, f"{field}: {first['msg']}.")


@app.get("/api/listings/search")
def search_listings(
    min_price: float | None = Query(None, alias="minPrice"),
    max_price: float | None = Query(None, alias="maxPrice"),
    min_bedrooms: int | None = Query(None, alias="minBedrooms"),
    city: str | None = None,
    keyword: str | None = None,
    target_budget: float | None = Query(None, alias="targetBudget"),
    page: int = 1,
    page_size: int = Query(10, alias="pageSize"),
    today: date = Depends(get_today),
) -> dict:
    params = SearchParams(
        min_price=min_price,
        max_price=max_price,
        min_bedrooms=min_bedrooms,
        city=city,
        keyword=keyword,
        target_budget=target_budget,
        page=page,
        page_size=page_size,
    )
    result = search(LISTINGS, params, today)
    return {
        "results": [{**item.listing.to_dict(), "score": item.score} for item in result.results],
        "page": result.page,
        "pageSize": result.page_size,
        "totalResults": result.total_results,
        "totalPages": result.total_pages,
    }
