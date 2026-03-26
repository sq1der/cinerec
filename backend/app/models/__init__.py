# Импортируем все модели здесь — это важно для Alembic
from app.models.user import User
from app.models.movie import Movie
from app.models.rating import Rating, Watchlist

__all__ = ["User", "Movie", "Rating", "Watchlist"]