import json
from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_user, get_recommender
from app.core.redis import cache_get, cache_set
from app.models.user import User
from app.services.recommendation.hybrid import HybridRecommender
from app.schemas.recommendation import RecommendationResponse

router = APIRouter()

TRENDING_TTL = 600       # 10 минут
SIMILAR_TTL = 3600       # 1 час


@router.get("/personal", response_model=RecommendationResponse)
async def personal_recommendations(
    top_n: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    recommender: HybridRecommender = Depends(get_recommender),
):
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
    recommender: HybridRecommender = Depends(get_recommender),
):
    cache_key = f"similar:{movie_id}:{top_n}"
    cached = await cache_get(cache_key)
    if cached:
        items = json.loads(cached)
        return RecommendationResponse(
            items=items, count=len(items), algorithm="content_based"
        )

    items = await recommender.get_similar(movie_id, top_n)
    await cache_set(cache_key, json.dumps(items), ttl=SIMILAR_TTL)
    return RecommendationResponse(
        items=items, count=len(items), algorithm="content_based"
    )


@router.get("/trending", response_model=RecommendationResponse)
async def trending(
    top_n: int = Query(20, ge=1, le=100),
    recommender: HybridRecommender = Depends(get_recommender),
):
    cache_key = f"trending:{top_n}"
    cached = await cache_get(cache_key)
    if cached:
        items = json.loads(cached)
        return RecommendationResponse(
            items=items, count=len(items), algorithm="trending"
        )

    items = await recommender.get_trending(top_n)
    await cache_set(cache_key, json.dumps(items), ttl=TRENDING_TTL)
    return RecommendationResponse(
        items=items, count=len(items), algorithm="trending"
    )