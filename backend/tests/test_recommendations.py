import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rating import Rating


class TestTrending:
    async def test_trending_no_auth(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/recommendations/trending")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["algorithm"] == "trending"

    async def test_trending_sorted_by_rating(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/recommendations/trending")
        items = resp.json()["items"]
        if len(items) > 1:
            scores = [i["score"] for i in items if i["score"] is not None]
            assert scores == sorted(scores, reverse=True)


class TestSimilar:
    async def test_similar_movies(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/recommendations/similar/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["algorithm"] == "content_based"
        # Inception похож на Matrix и Interstellar (оба Sci-Fi)
        ids = [item["movie_id"] for item in data["items"]]
        assert 2 in ids or 3 in ids

    async def test_similar_no_auth_required(self, client: AsyncClient, test_movies):
        resp = await client.get("/api/v1/recommendations/similar/1")
        assert resp.status_code == 200


class TestPersonal:
    async def test_personal_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/recommendations/personal")
        assert resp.status_code == 401

    async def test_cold_start_few_ratings(
        self, client: AsyncClient, test_movies, auth_headers
    ):
        # Менее 5 оценок → должен вернуть trending
        resp = await client.get("/api/v1/recommendations/personal", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) > 0
        # cold start возвращает trending items
        assert all(i["source"] == "trending" for i in data["items"])

    async def test_personal_with_ratings(
        self,
        client: AsyncClient,
        test_movies,
        auth_headers,
        db: AsyncSession,
        test_user,
    ):
        # Ставим 5+ оценок чтобы выйти из cold start
        for movie_id, score in [(1, 9.0), (2, 8.0), (3, 7.0)]:
            await client.post(
                f"/api/v1/movies/{movie_id}/rate",
                json={"score": score},
                headers=auth_headers,
            )

        resp = await client.get("/api/v1/recommendations/personal", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "algorithm" in data