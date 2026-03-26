"""
Загружает 100 популярных фильмов через TMDB API.
Получи бесплатный ключ на https://www.themoviedb.org/settings/api
"""
import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal, engine, Base
from app.models.movie import Movie

TMDB_API_KEY = "ded4bd6f7cbdc67da0165c57f7715661"  # получи бесплатно на themoviedb.org
TMDB_URL = "https://api.themoviedb.org/3"


async def fetch_movies():
    movies = []
    async with httpx.AsyncClient() as client:
        for page in range(1, 6):  # 5 страниц × 20 = 100 фильмов
            resp = await client.get(
                f"{TMDB_URL}/movie/popular",
                params={"api_key": TMDB_API_KEY, "language": "ru-RU", "page": page},
            )
            data = resp.json()
            for m in data.get("results", []):
                # Получаем детали с жанрами
                detail = await client.get(
                    f"{TMDB_URL}/movie/{m['id']}",
                    params={"api_key": TMDB_API_KEY, "language": "ru-RU"},
                )
                d = detail.json()
                genres = [g["name"] for g in d.get("genres", [])]
                feature_text = f"{d.get('title', '')} {' '.join(genres)} {d.get('overview', '')}"

                movies.append(Movie(
                    id=d["id"],
                    title=d.get("title") or d.get("original_title", ""),
                    original_title=d.get("original_title"),
                    overview=d.get("overview"),
                    genres=genres,
                    year=int(d["release_date"][:4]) if d.get("release_date") else None,
                    rating=d.get("vote_average"),
                    vote_count=d.get("vote_count", 0),
                    poster_url=f"https://image.tmdb.org/t/p/w500{d['poster_path']}" if d.get("poster_path") else None,
                    feature_text=feature_text,
                ))
    return movies


async def seed():
    async with AsyncSessionLocal() as db:
        movies = await fetch_movies()
        for movie in movies:
            existing = await db.get(Movie, movie.id)
            if not existing:
                db.add(movie)
        await db.commit()
        print(f"✅ Добавлено {len(movies)} фильмов")


if __name__ == "__main__":
    asyncio.run(seed())