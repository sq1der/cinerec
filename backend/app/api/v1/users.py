from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.rating import Rating, Watchlist
from app.schemas.movie import RatingResponse

router = APIRouter()


@router.get("/me/ratings", response_model=dict)
async def get_my_ratings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(
        select(func.count(Rating.id)).where(Rating.user_id == current_user.id)
    )).scalar_one()

    result = await db.execute(
        select(Rating)
        .where(Rating.user_id == current_user.id)
        .order_by(Rating.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    ratings = result.scalars().all()

    return {
        "items": [RatingResponse.model_validate(r).model_dump(mode="json") for r in ratings],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": -(-total // page_size),
    }


@router.get("/me/watchlist")
async def get_my_watchlist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(
        select(func.count(Watchlist.id)).where(Watchlist.user_id == current_user.id)
    )).scalar_one()

    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.movie))
        .where(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.added_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    watchlist = result.scalars().all()

    return {
        "items": [
            {
                "movie_id": item.movie_id,
                "added_at": item.added_at.isoformat(),
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
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": -(-total // page_size),
    }