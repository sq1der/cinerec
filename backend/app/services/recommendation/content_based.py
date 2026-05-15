import os
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.movie import Movie

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "models")
_TFIDF_PATH = os.path.join(_MODELS_DIR, "tfidf_model_optimized.joblib")


class ContentBasedRecommender:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._matrix = None
        self._movie_ids: list[int] = []
        self._vectorizer = None

    def _load_pretrained(self) -> bool:
        path = os.path.normpath(_TFIDF_PATH)
        if not os.path.exists(path):
            return False
        data = joblib.load(path)
        self._vectorizer = data["vectorizer"]
        self._matrix = data["matrix"]
        self._movie_ids = list(data["movie_ids"])
        return True

    async def _build_matrix(self) -> None:
        if self._load_pretrained():
            return

        # Fallback: build from DB feature_text
        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
        )
        result = await self.db.execute(
            select(Movie.id, Movie.feature_text)
            .where(Movie.feature_text.isnot(None))
            .order_by(Movie.id)
        )
        rows = result.all()
        if not rows:
            self._matrix = None
            return
        self._movie_ids = [r.id for r in rows]
        texts = [r.feature_text or "" for r in rows]
        self._matrix = self._vectorizer.fit_transform(texts)

    async def get_similar(
        self, movie_id: int, top_n: int = 20
    ) -> list[tuple[int, float]]:
        if self._matrix is None:
            await self._build_matrix()

        if self._matrix is None or movie_id not in self._movie_ids:
            return []

        idx = self._movie_ids.index(movie_id)
        movie_vec = self._matrix[idx]

        scores = cosine_similarity(movie_vec, self._matrix).flatten()
        scores[idx] = 0

        top_indices = np.argsort(scores)[::-1][:top_n]
        return [
            (self._movie_ids[i], float(scores[i]))
            for i in top_indices
            if scores[i] > 0
        ]

    async def get_recommendations_for_user(
        self,
        liked_movie_ids: list[int],
        seen_movie_ids: set[int],
        top_n: int = 20,
    ) -> list[tuple[int, float]]:
        if self._matrix is None:
            await self._build_matrix()

        if self._matrix is None or not liked_movie_ids:
            return []

        indices = [
            self._movie_ids.index(mid)
            for mid in liked_movie_ids
            if mid in self._movie_ids
        ]
        if not indices:
            return []

        user_profile = np.asarray(self._matrix[indices].mean(axis=0))
        scores = cosine_similarity(user_profile, self._matrix).flatten()

        result = []
        for i in np.argsort(scores)[::-1]:
            mid = self._movie_ids[i]
            if mid not in seen_movie_ids and scores[i] > 0:
                result.append((mid, float(scores[i])))
            if len(result) >= top_n:
                break

        return result
