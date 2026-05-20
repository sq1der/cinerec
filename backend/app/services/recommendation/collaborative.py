import os
import uuid
import joblib
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rating import Rating

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "models")
_SVD_PATH = os.path.join(_MODELS_DIR, "surprise_svd_optimized.joblib")


class SVDModelData:
    """Данные предобученной модели — загружаются один раз при старте."""
    def __init__(self):
        path = os.path.normpath(_SVD_PATH)
        if not os.path.exists(path):
            self.item_factors = None
            self.item_biases = None
            self.movie_ids = []
            self.id_set = set()
            self.inner_map = {}
            return
        data = joblib.load(path)
        algo = data["algo"]
        ts = algo.trainset
        self.movie_ids = [ts.to_raw_iid(i) for i in range(ts.n_items)]
        self.inner_map = {raw: i for i, raw in enumerate(self.movie_ids)}
        self.id_set = set(self.movie_ids)
        self.item_factors = algo.qi
        self.item_biases = algo.bi


class CollaborativeRecommender:
    def __init__(self, db: AsyncSession, model: SVDModelData | None = None):
        self.db = db
        self._model = model
        self._predictions: np.ndarray | None = None
        self._user_ids: list[str] = []
        self._movie_ids: list[int] = []

    async def _build_matrix(self) -> None:
        """Fallback — строит SVD из оценок в БД."""
        result = await self.db.execute(
            select(Rating.user_id, Rating.movie_id, Rating.score)
        )
        ratings = result.all()
        if len(ratings) < 10:
            self._predictions = None
            return
        self._user_ids = list({str(r.user_id) for r in ratings})
        self._movie_ids = list({r.movie_id for r in ratings})
        user_idx = {uid: i for i, uid in enumerate(self._user_ids)}
        movie_idx = {mid: i for i, mid in enumerate(self._movie_ids)}
        rows = [user_idx[str(r.user_id)] for r in ratings]
        cols = [movie_idx[r.movie_id] for r in ratings]
        n_users, n_movies = len(self._user_ids), len(self._movie_ids)
        matrix = csr_matrix(
            ([r.score for r in ratings], (rows, cols)),
            shape=(n_users, n_movies),
            dtype=np.float32,
        )
        matrix_dense = matrix.toarray()
        user_means = np.true_divide(
            matrix_dense.sum(axis=1),
            (matrix_dense != 0).sum(axis=1),
            where=(matrix_dense != 0).sum(axis=1) != 0,
        )
        matrix_norm = matrix_dense.copy()
        for i, mean in enumerate(user_means):
            matrix_norm[i, matrix_dense[i] != 0] -= mean
        k = min(50, n_users - 1, n_movies - 1)
        if k < 1:
            self._predictions = None
            return
        U, sigma, Vt = svds(csr_matrix(matrix_norm), k=k)
        self._predictions = np.dot(np.dot(U, np.diag(sigma)), Vt)
        for i, mean in enumerate(user_means):
            self._predictions[i] += mean

    async def get_recommendations(
        self,
        user_id: str,
        seen_movie_ids: set[int],
        top_n: int = 20,
    ) -> list[tuple[int, float]]:
        if self._model and self._model.item_factors is not None:
            return await self._get_svd_item_recs(user_id, seen_movie_ids, top_n)
        if self._predictions is None:
            await self._build_matrix()
        if self._predictions is None or user_id not in self._user_ids:
            return []
        user_idx = self._user_ids.index(user_id)
        user_preds = self._predictions[user_idx]
        result = []
        for movie_idx in np.argsort(user_preds)[::-1]:
            mid = self._movie_ids[movie_idx]
            if mid not in seen_movie_ids:
                result.append((mid, float(user_preds[movie_idx])))
            if len(result) >= top_n:
                break
        return result

    async def _get_svd_item_recs(
        self,
        user_id: str,
        seen_movie_ids: set[int],
        top_n: int,
    ) -> list[tuple[int, float]]:
        m = self._model
        result = await self.db.execute(
            select(Rating.movie_id, Rating.score).where(
                Rating.user_id == uuid.UUID(user_id)
            )
        )
        user_ratings = result.all()
        if not user_ratings:
            available = [
                (mid, float(m.item_biases[m.inner_map[mid]]))
                for mid in m.movie_ids
                if mid not in seen_movie_ids
            ]
            available.sort(key=lambda x: x[1], reverse=True)
            return available[:top_n]
        liked = [r for r in user_ratings if r.movie_id in m.id_set and r.score >= 7.0]
        if not liked:
            liked = [r for r in user_ratings if r.movie_id in m.id_set]
        if not liked:
            return []
        weights = np.array([r.score for r in liked], dtype=np.float32)
        weights /= weights.sum()
        inner_ids = [m.inner_map[r.movie_id] for r in liked]
        user_vec = (m.item_factors[inner_ids] * weights[:, None]).sum(
            axis=0, keepdims=True
        )
        scores = cosine_similarity(user_vec, m.item_factors).flatten()
        recs = []
        for i in np.argsort(scores)[::-1]:
            mid = m.movie_ids[i]
            if mid not in seen_movie_ids and scores[i] > 0:
                recs.append((mid, float(scores[i])))
            if len(recs) >= top_n:
                break
        return recs