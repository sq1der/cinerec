from pydantic import BaseModel


class RecommendationItem(BaseModel):
    movie_id: int
    title: str | None = None
    score: float | None = None
    source: str  # "hybrid" | "content" | "collaborative" | "trending"


class RecommendationResponse(BaseModel):
    items: list[RecommendationItem]
    count: int
    algorithm: str