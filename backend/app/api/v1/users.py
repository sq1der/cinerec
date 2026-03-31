from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.rating import Rating, Watchlist
from app.schemas.movie import RatingResponse, WatchlistResponse

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


@router.get("/me/watchlist", response_model=list[WatchlistResponse])
async def get_my_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Watchlist текущего пользователя."""
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc())
    )
    return result.scalars().all()