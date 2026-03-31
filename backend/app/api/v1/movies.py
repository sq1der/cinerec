from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.movie_service import MovieService
from app.repositories.movie_repository import MovieRepository 
from app.schemas.movie import (
    MovieResponse,
    MovieListResponse,
    RatingRequest,
    RatingResponse,
)
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/", response_model=MovieListResponse)
async def get_movies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    genre: str | None = Query(None),
    year: int | None = Query(None),
    min_rating: float | None = Query(None, ge=1.0, le=10.0),
    db: AsyncSession = Depends(get_db),
):
    service = MovieService(db)
    return await service.get_list(page, page_size, genre, year, min_rating)


@router.get("/search", response_model=list[MovieResponse])
async def search_movies(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
):
    service = MovieService(db)
    return await service.search(q)


@router.get("/{movie_id}/rate", response_model=RatingResponse)
async def get_my_rating(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = MovieRepository(db)
    rating = await repo.get_rating(current_user.id, movie_id)
    if not rating:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You haven't rated this movie yet",
        )
    return rating


@router.get("/{movie_id}/ratings/all")
async def get_movie_ratings(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = MovieService(db)
    movie = await service.get_by_id(movie_id)
    return {
        "movie_id": movie_id,
        "rating": movie.rating,
        "vote_count": movie.vote_count,
    }


@router.post("/{movie_id}/rate", response_model=RatingResponse)
async def rate_movie(
    movie_id: int,
    data: RatingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MovieService(db)
    return await service.rate_movie(current_user.id, movie_id, data.score)


@router.post("/{movie_id}/watchlist")
async def toggle_watchlist(
    movie_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = MovieService(db)
    return await service.toggle_watchlist(current_user.id, movie_id)


@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    service = MovieService(db)
    return await service.get_by_id(movie_id)