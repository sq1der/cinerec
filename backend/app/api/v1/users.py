from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.rating import Rating, Watchlist
from app.schemas.movie import RatingResponse

router = APIRouter()


@router.get("/me/ratings", response_model=list[RatingResponse])
async def get_my_ratings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Все оценки текущего пользователя."""
    result = await db.execute(
        select(Rating)
        .where(Rating.user_id == current_user.id)
        .order_by(Rating.created_at.desc())
    )
    return result.scalars().all()


@router.get("/me/watchlist")             
async def get_my_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.movie))
        .where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc())
    )
    watchlist = result.scalars().all()

    return [
        {
            "movie_id": item.movie_id,
            "added_at": item.added_at,
            "movie": {
                "id": item.movie.id,
                "title": item.movie.title,
                "genres": item.movie.genres,
                "year": item.movie.year,
                "rating": item.movie.rating,
                "poster_url": item.movie.poster_url,
            } if item.movie else None,
        }
        for item in watchlist
    ]