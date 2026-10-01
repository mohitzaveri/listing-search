from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_today

URL = "/api/listings/search"


@pytest.fixture
def client():
    app.dependency_overrides[get_today] = lambda: date(2026, 9, 30)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_search_returns_a_ranked_page_with_totals(client):
    response = client.get(URL, params={"targetBudget": 450000, "pageSize": 5})
    assert response.status_code == 200
    body = response.json()
    assert (body["page"], body["pageSize"], body["totalResults"], body["totalPages"]) == (1, 5, 12, 3)
    assert len(body["results"]) == 5
    scores = [item["score"] for item in body["results"]]
    assert scores == sorted(scores, reverse=True)
    assert {"address", "price", "bedrooms", "score", "listedDate", "status"} <= body["results"][0].keys()


def test_filters_are_applied(client):
    body = client.get(URL, params={"city": "springfield", "minBedrooms": 3, "keyword": "kitchen"}).json()
    assert sorted(item["id"] for item in body["results"]) == ["A2", "B8"]


def test_no_matches_is_200_with_empty_results(client):
    response = client.get(URL, params={"city": "Fairfax", "minBedrooms": 5})
    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["totalResults"] == 0


@pytest.mark.parametrize(
    "params, field",
    [
        ({"minPrice": 500000, "maxPrice": 400000}, "minPrice"),
        ({"pageSize": 0}, "pageSize"),
        ({"pageSize": -1}, "pageSize"),
        ({"page": 0}, "page"),
        ({"page": 99}, "page"),
        ({"city": "Bostn"}, "city"),
        ({"minPrice": "abc"}, "minPrice"),
        ({"minBedrooms": "2.5"}, "minBedrooms"),
        ({"targetBudget": "0"}, "targetBudget"),
    ],
)
def test_bad_input_returns_400_with_field_and_message(client, params, field):
    response = client.get(URL, params=params)
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["field"] == field
    assert error["message"]
