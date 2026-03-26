from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.recommendation.hybrid import HybridRecommender
from app.schemas.recommendation import RecommendationResponse

router = APIRouter()


@router.get("/personal", response_model=RecommendationResponse)
async def personal_recommendations(
    top_n: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recommender = HybridRecommender(db)
    items = await recommender.get_personal(current_user.id, top_n)
    return RecommendationResponse(
        items=items,
        count=len(items),
        algorithm="hybrid" if len(items) > 0 else "cold_start",
    )


@router.get("/similar/{movie_id}", response_model=RecommendationResponse)
async def similar_movies(
    movie_id: int,
    top_n: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    recommender = HybridRecommender(db)
    items = await recommender.get_similar(movie_id, top_n)
    return RecommendationResponse(
        items=items,
        count=len(items),
        algorithm="content_based",
    )


@router.get("/trending", response_model=RecommendationResponse)
async def trending(
    top_n: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    recommender = HybridRecommender(db)
    items = await recommender._get_trending(top_n)
    return RecommendationResponse(
        items=items,
        count=len(items),
        algorithm="trending",
    )