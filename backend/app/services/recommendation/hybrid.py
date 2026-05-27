import uuid
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rating import Rating
from app.models.movie import Movie
from app.core.logging import get_logger
from app.services.recommendation.content_based import ContentBasedRecommender, TFIDFModelData
from app.services.recommendation.collaborative import CollaborativeRecommender, SVDModelData

logger = get_logger("app.recommender")


class HybridRecommender:
    COLD_START_THRESHOLD = 5

    def __init__(
        self,
        db: AsyncSession,
        tfidf_model: TFIDFModelData | None = None,
        svd_model: SVDModelData | None = None,
    ):
        self.db = db
        self.content = ContentBasedRecommender(db, tfidf_model)
        self.collab = CollaborativeRecommender(db, svd_model)

    async def _get_user_ratings(self, user_id: uuid.UUID) -> list[Rating]:
        result = await self.db.execute(
            select(Rating)
            .where(Rating.user_id == user_id)
            .order_by(Rating.score.desc())
        )
        return result.scalars().all()

    def _get_weights(self, rating_count: int) -> tuple[float, float]:
        if rating_count < 5:
            return 1.0, 0.0
        elif rating_count < 20:
            return 0.6, 0.4
        else:
            return 0.3, 0.7

    async def get_personal(self, user_id: uuid.UUID, top_n: int = 20) -> list[dict]:
        t0 = time.perf_counter()
        ratings = await self._get_user_ratings(user_id)
        if len(ratings) < self.COLD_START_THRESHOLD:
            result = await self.get_trending(top_n)
            logger.info(f"personal:{user_id} → cold_start ({len(result)} items, {(time.perf_counter()-t0)*1000:.1f}ms)")
            return result

        seen_ids = {r.movie_id for r in ratings}
        liked_ids = [r.movie_id for r in ratings if r.score >= 7.0] or [
            r.movie_id for r in ratings[:5]
        ]
        content_weight, collab_weight = self._get_weights(len(ratings))
        content_recs = await self.content.get_recommendations_for_user(
            liked_ids, seen_ids, top_n=top_n * 2
        )
        collab_recs = await self.collab.get_recommendations(
            str(user_id), seen_ids, top_n=top_n * 2
        )
        merged = self._merge(content_recs, collab_recs, content_weight, collab_weight, top_n)
        result = await self._enrich_merged(merged)
        logger.info(
            f"personal:{user_id} → hybrid (content={content_weight}, collab={collab_weight}, "
            f"{len(result)} items, {(time.perf_counter()-t0)*1000:.1f}ms)"
        )
        return result

    async def get_similar(self, movie_id: int, top_n: int = 20) -> list[dict]:
        recs = await self.content.get_similar(movie_id, top_n)
        return await self._enrich(recs)

    async def get_trending(self, top_n: int = 20) -> list[dict]:
        result = await self.db.execute(
            select(Movie)
            .where(Movie.vote_count > 100)
            .order_by(Movie.rating.desc(), Movie.vote_count.desc())
            .limit(top_n)
        )
        return [
            {"movie_id": m.id, "title": m.title, "poster_url": m.poster_url,
             "score": m.rating, "source": "trending"}
            for m in result.scalars().all()
        ]

    def _merge(self, content_recs, collab_recs, content_w, collab_w, top_n) -> list[dict]:
        def normalize(recs):
            if not recs:
                return {}
            scores = [s for _, s in recs]
            rng = (max(scores) - min(scores)) or 1
            return {mid: (s - min(scores)) / rng for mid, s in recs}

        content_norm = normalize(content_recs)
        collab_norm = normalize(collab_recs)
        all_ids = set(content_norm) | set(collab_norm)
        merged = {
            mid: content_w * content_norm.get(mid, 0) + collab_w * collab_norm.get(mid, 0)
            for mid in all_ids
        }
        top = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:top_n]
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

    async def _enrich_merged(self, recs: list[dict]) -> list[dict]:
        if not recs:
            return []
        ids = [r["movie_id"] for r in recs]
        result = await self.db.execute(select(Movie).where(Movie.id.in_(ids)))
        movies = {m.id: m for m in result.scalars().all()}
        return [
            {
                "movie_id": r["movie_id"],
                "title": movies[r["movie_id"]].title,
                "poster_url": movies[r["movie_id"]].poster_url,
                "score": r["score"],
                "source": r["source"],
            }
            for r in recs
            if r["movie_id"] in movies
        ]

    async def _enrich(self, recs: list[tuple[int, float]]) -> list[dict]:
        if not recs:
            return []
        ids = [mid for mid, _ in recs]
        result = await self.db.execute(select(Movie).where(Movie.id.in_(ids)))
        movies = {m.id: m for m in result.scalars().all()}
        return [
            {
                "movie_id": mid,
                "title": movies[mid].title,
                "poster_url": movies[mid].poster_url,
                "score": round(score, 4),
                "source": "content",
            }
            for mid, score in recs
            if mid in movies
        ]