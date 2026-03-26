from datetime import datetime
from pydantic import BaseModel, Field


class MovieResponse(BaseModel):
    id: int
    title: str
    original_title: str | None
    overview: str | None
    genres: list[str]
    year: int | None
    rating: float | None
    vote_count: int
    poster_url: str | None

    model_config = {"from_attributes": True}


class MovieListResponse(BaseModel):
    items: list[MovieResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RatingRequest(BaseModel):
    score: float = Field(..., ge=1.0, le=10.0)


class RatingResponse(BaseModel):
    movie_id: int
    score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchlistResponse(BaseModel):
    movie_id: int
    added_at: datetime
    movie: MovieResponse

    model_config = {"from_attributes": True}