import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.rating import Rating


class CollaborativeRecommender:
    """
    SVD на матрице user × movie.
    Предсказывает оценки для фильмов которые пользователь не видел.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._predictions: np.ndarray | None = None
        self._user_ids: list[str] = []
        self._movie_ids: list[int] = []

    async def _build_matrix(self) -> None:
        """Загружает все оценки и строит матрицу."""
        result = await self.db.execute(
            select(Rating.user_id, Rating.movie_id, Rating.score)
        )
        ratings = result.all()

        if len(ratings) < 10:
            # Недостаточно данных для SVD
            self._predictions = None
            return

        # Собираем уникальные id
        self._user_ids = list({str(r.user_id) for r in ratings})
        self._movie_ids = list({r.movie_id for r in ratings})

        user_idx = {uid: i for i, uid in enumerate(self._user_ids)}
        movie_idx = {mid: i for i, mid in enumerate(self._movie_ids)}

        rows = [user_idx[str(r.user_id)] for r in ratings]
        cols = [movie_idx[r.movie_id] for r in ratings]
        data = [r.score for r in ratings]

        n_users = len(self._user_ids)
        n_movies = len(self._movie_ids)
        matrix = csr_matrix(
            (data, (rows, cols)), shape=(n_users, n_movies), dtype=np.float32
        )

        # Нормализация: вычитаем среднее по строке (пользователю)
        matrix_dense = matrix.toarray()
        user_means = np.true_divide(
            matrix_dense.sum(axis=1),
            (matrix_dense != 0).sum(axis=1),
            where=(matrix_dense != 0).sum(axis=1) != 0,
        )
        matrix_norm = matrix_dense.copy()
        for i, mean in enumerate(user_means):
            mask = matrix_dense[i] != 0
            matrix_norm[i, mask] -= mean

        # SVD — k факторов
        k = min(50, n_users - 1, n_movies - 1)
        if k < 1:
            self._predictions = None
            return

        U, sigma, Vt = svds(csr_matrix(matrix_norm), k=k)
        sigma_diag = np.diag(sigma)

        # Восстанавливаем матрицу и добавляем средние обратно
        self._predictions = np.dot(np.dot(U, sigma_diag), Vt)
        for i, mean in enumerate(user_means):
            self._predictions[i] += mean

    async def get_recommendations(
        self,
        user_id: str,
        seen_movie_ids: set[int],
        top_n: int = 20,
    ) -> list[tuple[int, float]]:
        """
        Возвращает список (movie_id, predicted_score).
        """
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