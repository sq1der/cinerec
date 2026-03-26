from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.movie_repository import MovieRepository
from app.schemas.movie import MovieListResponse
import uuid
import math


class MovieService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MovieRepository(db)

    async def get_list(
        self,
        page: int,
        page_size: int,
        genre: str | None,
        year: int | None,
        min_rating: float | None,
    ) -> MovieListResponse:
        movies, total = await self.repo.get_list(
            page=page,
            page_size=page_size,
            genre=genre,
            year=year,
            min_rating=min_rating,
        )
        return MovieListResponse(
            items=movies,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )

    async def get_by_id(self, movie_id: int):
        movie = await self.repo.get_by_id(movie_id)
        if not movie:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Movie {movie_id} not found",
            )
        return movie

    async def search(self, q: str):
        if len(q.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Query must be at least 2 characters",
            )
        return await self.repo.search(q)

    async def rate_movie(
        self, user_id: uuid.UUID, movie_id: int, score: float
    ):
        await self.get_by_id(movie_id)  # проверяем что фильм существует
        return await self.repo.upsert_rating(user_id, movie_id, score)

    async def toggle_watchlist(self, user_id: uuid.UUID, movie_id: int):
        await self.get_by_id(movie_id)
        return await self.repo.toggle_watchlist(user_id, movie_id)

    async def get_watchlist(self, user_id: uuid.UUID):
        return await self.repo.get_watchlist(user_id)