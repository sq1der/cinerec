"""
Загружает фильмы из ratings_tmdb.csv (9715 уникальных фильмов).
feature_text берётся из cleaned_movies.csv если есть, иначе генерируется из деталей TMDB.

Запуск:
    python -m scripts.seed_movies \
        --ratings /path/to/ratings_tmdb.csv \
        --movies /path/to/cleaned_movies.csv
"""
import asyncio
import argparse
import httpx
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal
from app.models.movie import Movie
from app.config import settings


TMDB_URL = "https://api.themoviedb.org/3"
BATCH_SIZE = 40       # TMDB rate limit: 40 req / 10 sec
BATCH_DELAY = 10.0    # секунд между батчами


async def fetch_movie_details(
    client: httpx.AsyncClient,
    movie_id: int,
    feature_texts: dict[int, str],
) -> Movie | None:
    try:
        resp = await client.get(
            f"{TMDB_URL}/movie/{movie_id}",
            params={"api_key": settings.TMDB_API_KEY, "language": "en-US"},
            timeout=10.0,
        )
        if resp.status_code != 200:
            print(f"  ⚠ TMDB {movie_id}: status {resp.status_code}")
            return None

        d = resp.json()
        genres = [g["name"] for g in d.get("genres", [])]

        # feature_text из датасета если есть, иначе генерируем
        feature_text = feature_texts.get(
            movie_id,
            f"{d.get('title', '')} {' '.join(genres)} {d.get('overview', '')}",
        )

        return Movie(
            id=d["id"],
            title=d.get("title") or d.get("original_title", ""),
            original_title=d.get("original_title"),
            overview=d.get("overview"),
            genres=genres,
            year=int(d["release_date"][:4]) if d.get("release_date") else None,
            rating=d.get("vote_average"),
            vote_count=d.get("vote_count", 0),
            poster_url=(
                f"https://image.tmdb.org/t/p/w500{d['poster_path']}"
                if d.get("poster_path") else None
            ),
            feature_text=feature_text,
        )
    except Exception as e:
        print(f"  ✗ Error fetching {movie_id}: {e}")
        return None


async def seed(ratings_path: str, movies_path: str) -> None:
    # Загружаем датасеты
    print("📂 Loading datasets...")
    ratings_df = pd.read_csv(ratings_path)
    movies_df = pd.read_csv(movies_path)

    movie_ids = list(ratings_df["movieId"].unique())
    feature_texts = dict(zip(movies_df["movie_id"], movies_df["feature_text"]))

    print(f"🎬 Total unique movies to load: {len(movie_ids)}")
    print(f"✅ feature_text from dataset: {sum(1 for mid in movie_ids if mid in feature_texts)}")
    print(f"🌐 Need to generate from TMDB: {sum(1 for mid in movie_ids if mid not in feature_texts)}")
    print()

    async with AsyncSessionLocal() as db:
        # Проверяем сколько уже в БД
        from sqlalchemy import select, func
        existing_count = (await db.execute(select(func.count(Movie.id)))).scalar_one()
        print(f"📊 Already in DB: {existing_count} movies")

        existing_ids_result = await db.execute(select(Movie.id))
        existing_ids = {row[0] for row in existing_ids_result.all()}
        to_fetch = [mid for mid in movie_ids if mid not in existing_ids]

        if not to_fetch:
            print("✅ All movies already in DB, nothing to do.")
            return

        print(f"🔄 Need to fetch: {len(to_fetch)} movies")
        print()

        added = 0
        failed = 0

        async with httpx.AsyncClient() as client:
            for batch_start in range(0, len(to_fetch), BATCH_SIZE):
                batch = to_fetch[batch_start:batch_start + BATCH_SIZE]
                batch_num = batch_start // BATCH_SIZE + 1
                total_batches = (len(to_fetch) + BATCH_SIZE - 1) // BATCH_SIZE

                print(f"Batch {batch_num}/{total_batches} — fetching {len(batch)} movies...")

                tasks = [
                    fetch_movie_details(client, mid, feature_texts)
                    for mid in batch
                ]
                results = await asyncio.gather(*tasks)

                for movie in results:
                    if movie:
                        db.add(movie)
                        added += 1
                    else:
                        failed += 1

                await db.commit()
                print(f"  ✓ Saved batch {batch_num} ({added} total added)")

                # Пауза между батчами кроме последнего
                if batch_start + BATCH_SIZE < len(to_fetch):
                    print(f"  ⏳ Waiting {BATCH_DELAY}s (TMDB rate limit)...")
                    await asyncio.sleep(BATCH_DELAY)

    print()
    print(f"✅ Done! Added: {added}, Failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ratings",
        default="/Users/amanbelgibay/Downloads/ratings_tmdb.csv",
    )
    parser.add_argument(
        "--movies",
        default="/Users/amanbelgibay/Downloads/cleaned_movies.csv",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.ratings, args.movies))