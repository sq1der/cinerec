from sqlalchemy import select, func, or_, delete, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.movie import Movie
from app.models.rating import Rating, Watchlist
import uuid


class MovieRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, movie_id: int) -> Movie | None:
        result = await self.db.execute(
            select(Movie).where(Movie.id == movie_id)
        )
        return result.scalar_one_or_none()

    async def get_list(
        self,
        page: int = 1,
        page_size: int = 20,
        genre: str | None = None,
        year: int | None = None,
        min_rating: float | None = None,
    ) -> tuple[list[Movie], int]:
        query = select(Movie)

        if genre:
            # Совместимо и с PostgreSQL (JSON) и с SQLite
            query = query.where(
                cast(Movie.genres, String).ilike(f"%{genre}%")
            )
        if year:
            query = query.where(Movie.year == year)
        if min_rating:
            query = query.where(Movie.rating >= min_rating)

        # Считаем total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        # Пагинация
        query = (
            query
            .order_by(Movie.vote_count.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def search(self, q: str, limit: int = 20) -> list[Movie]:
        result = await self.db.execute(
            select(Movie)
            .where(
                or_(
                    Movie.title.ilike(f"%{q}%"),
                    Movie.original_title.ilike(f"%{q}%"),
                )
            )
            .order_by(Movie.vote_count.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # --- Ratings ---

    async def get_rating(self, user_id: uuid.UUID, movie_id: int) -> Rating | None:
        result = await self.db.execute(
            select(Rating).where(
                Rating.user_id == user_id,
                Rating.movie_id == movie_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_rating(
        self, user_id: uuid.UUID, movie_id: int, score: float
    ) -> Rating:
        rating = await self.get_rating(user_id, movie_id)
        if rating:
            rating.score = score
        else:
            rating = Rating(user_id=user_id, movie_id=movie_id, score=score)
            self.db.add(rating)
        await self.db.flush()
        await self.db.refresh(rating)
        # Обновляем средний рейтинг фильма
        await self._update_movie_rating(movie_id)
        return rating

    async def _update_movie_rating(self, movie_id: int) -> None:
        result = await self.db.execute(
            select(func.avg(Rating.score), func.count(Rating.id))
            .where(Rating.movie_id == movie_id)
        )
        avg, count = result.one()
        movie = await self.get_by_id(movie_id)
        if movie:
            movie.rating = round(float(avg), 2) if avg else None
            movie.vote_count = count or 0

    # --- Watchlist ---

    async def get_watchlist(self, user_id: uuid.UUID) -> list[Watchlist]:
        result = await self.db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.added_at.desc())
        )
        return result.scalars().all()

    async def toggle_watchlist(
        self, user_id: uuid.UUID, movie_id: int
    ) -> dict:
        existing = await self.db.execute(
            select(Watchlist).where(
                Watchlist.user_id == user_id,
                Watchlist.movie_id == movie_id,
            )
        )
        item = existing.scalar_one_or_none()

        if item:
            await self.db.execute(
                delete(Watchlist).where(
                    Watchlist.user_id == user_id,
                    Watchlist.movie_id == movie_id,
                )
            )
            return {"action": "removed", "movie_id": movie_id}
        else:
            self.db.add(Watchlist(user_id=user_id, movie_id=movie_id))
            return {"action": "added", "movie_id": movie_id}