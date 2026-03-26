import pytest
from httpx import AsyncClient


class TestCatalog:
    async def test_get_movies(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/movies/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 3
        assert data["page"] == 1

    async def test_pagination(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/movies/?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["pages"] == 2

    async def test_filter_by_genre(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/movies/?genre=Drama")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all("Drama" in m["genres"] for m in items)

    async def test_filter_by_min_rating(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/movies/?min_rating=8.7")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(m["rating"] >= 8.7 for m in items)

    async def test_get_movie_by_id(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/movies/1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Inception"

    async def test_get_movie_not_found(self, client: AsyncClient):
        resp = await client.get("/api/v1/movies/99999")
        assert resp.status_code == 404


class TestSearch:
    async def test_search_by_title(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/movies/search?q=matrix")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
        assert any("Matrix" in m["title"] for m in results)

    async def test_search_too_short(self, client: AsyncClient):
        resp = await client.get("/api/v1/movies/search?q=a")
        assert resp.status_code == 422

    async def test_search_no_results(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/movies/search?q=xyznotexist")
        assert resp.status_code == 200
        assert resp.json() == []


class TestRatings:
    async def test_rate_movie(self, client: AsyncClient, test_movies, auth_headers):
        resp = await client.post(
            "/api/v1/movies/1/rate",
            json={"score": 9.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["score"] == 9.0

    async def test_rate_updates_existing(self, client: AsyncClient, test_movies, auth_headers):
        await client.post("/api/v1/movies/1/rate", json={"score": 7.0}, headers=auth_headers)
        resp = await client.post("/api/v1/movies/1/rate", json={"score": 5.0}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["score"] == 5.0

    async def test_rate_invalid_score(self, client: AsyncClient, test_movies, auth_headers):
        resp = await client.post(
            "/api/v1/movies/1/rate",
            json={"score": 11.0},  # выше максимума
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_rate_unauthorized(self, client: AsyncClient, test_movies):
        resp = await client.post("/api/v1/movies/1/rate", json={"score": 9.0})
        assert resp.status_code == 401


class TestWatchlist:
    async def test_add_to_watchlist(self, client: AsyncClient, test_movies, auth_headers):
        resp = await client.post("/api/v1/movies/1/watchlist", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["action"] == "added"

    async def test_remove_from_watchlist(self, client: AsyncClient, test_movies, auth_headers):
        await client.post("/api/v1/movies/1/watchlist", headers=auth_headers)
        resp = await client.post("/api/v1/movies/1/watchlist", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["action"] == "removed"

    async def test_watchlist_unauthorized(self, client: AsyncClient, test_movies):
        resp = await client.post("/api/v1/movies/1/watchlist")
        assert resp.status_code == 401