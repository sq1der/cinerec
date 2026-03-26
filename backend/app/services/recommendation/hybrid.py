import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rating import Rating
from app.models.movie import Movie
from app.services.recommendation.content_based import ContentBasedRecommender
from app.services.recommendation.collaborative import CollaborativeRecommender


class HybridRecommender:
    """
    Объединяет content-based и collaborative.
    Вес collaborative растёт с количеством оценок пользователя:
      < 5  оценок → cold start (trending)
      5-20 оценок → больше content (0.6 / 0.4)
      20+  оценок → больше collaborative (0.3 / 0.7)
    """

    COLD_START_THRESHOLD = 5

    def __init__(self, db: AsyncSession):
        self.db = db
        self.content = ContentBasedRecommender(db)
        self.collab = CollaborativeRecommender(db)

    async def _get_user_ratings(self, user_id: uuid.UUID) -> list[Rating]:
        result = await self.db.execute(
            select(Rating)
            .where(Rating.user_id == user_id)
            .order_by(Rating.score.desc())
        )
        return result.scalars().all()

    def _get_weights(self, rating_count: int) -> tuple[float, float]:
        """Возвращает (content_weight, collab_weight)."""
        if rating_count < 5:
            return 1.0, 0.0
        elif rating_count < 20:
            return 0.6, 0.4
        else:
            return 0.3, 0.7

    async def get_personal(
        self, user_id: uuid.UUID, top_n: int = 20
    ) -> list[dict]:
        ratings = await self._get_user_ratings(user_id)

        if len(ratings) < self.COLD_START_THRESHOLD:
            return await self._get_trending(top_n)

        seen_ids = {r.movie_id for r in ratings}
        liked_ids = [r.movie_id for r in ratings if r.score >= 7.0]
        if not liked_ids:
            liked_ids = [r.movie_id for r in ratings[:5]]

        content_weight, collab_weight = self._get_weights(len(ratings))

        # Получаем рекомендации от обоих алгоритмов
        content_recs = await self.content.get_recommendations_for_user(
            liked_ids, seen_ids, top_n=top_n * 2
        )
        collab_recs = await self.collab.get_recommendations(
            str(user_id), seen_ids, top_n=top_n * 2
        )

        return self._merge(
            content_recs, collab_recs,
            content_weight, collab_weight,
            top_n,
        )

    async def get_similar(
        self, movie_id: int, top_n: int = 20
    ) -> list[dict]:
        recs = await self.content.get_similar(movie_id, top_n)
        return await self._enrich(recs)

    async def _get_trending(self, top_n: int) -> list[dict]:
        """Cold start — популярные фильмы по vote_count и рейтингу."""
        result = await self.db.execute(
            select(Movie)
            .where(Movie.vote_count > 100)
            .order_by(Movie.rating.desc(), Movie.vote_count.desc())
            .limit(top_n)
        )
        movies = result.scalars().all()
        return [
            {
                "movie_id": m.id,
                "title": m.title,
                "score": m.rating,
                "source": "trending",
            }
            for m in movies
        ]

    def _merge(
        self,
        content_recs: list[tuple[int, float]],
        collab_recs: list[tuple[int, float]],
        content_w: float,
        collab_w: float,
        top_n: int,
    ) -> list[dict]:
        """Нормализует и объединяет скоры двух алгоритмов."""

        def normalize(recs: list[tuple[int, float]]) -> dict[int, float]:
            if not recs:
                return {}
            scores = [s for _, s in recs]
            min_s, max_s = min(scores), max(scores)
            rng = max_s - min_s or 1
            return {mid: (s - min_s) / rng for mid, s in recs}

        content_norm = normalize(content_recs)
        collab_norm = normalize(collab_recs)

        all_ids = set(content_norm) | set(collab_norm)
        merged = {}
        for mid in all_ids:
            merged[mid] = (
                content_w * content_norm.get(mid, 0)
                + collab_w * collab_norm.get(mid, 0)
            )

        top = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:top_n]

        # Определяем источник для прозрачности
        result = []
        for mid, score in top:
            if mid in content_norm and mid in collab_norm:
                source = "hybrid"
            elif mid in collab_norm:
                source = "collaborative"
            else:
                source = "content"
            result.append({"movie_id": mid, "score": round(score, 4), "source": source})

        return result

    async def _enrich(
        self, recs: list[tuple[int, float]]
    ) -> list[dict]:
        """Добавляет title к результатам content-based."""
        if not recs:
            return []
        ids = [mid for mid, _ in recs]
        result = await self.db.execute(
            select(Movie).where(Movie.id.in_(ids))
        )
        movies = {m.id: m for m in result.scalars().all()}
        return [
            {
                "movie_id": mid,
                "title": movies[mid].title if mid in movies else None,
                "score": round(score, 4),
                "source": "content",
            }
            for mid, score in recs
            if mid in movies
        ]