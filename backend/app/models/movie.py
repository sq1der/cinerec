from sqlalchemy import String, Text, Float, Integer, DateTime, func, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    original_title: Mapped[str | None] = mapped_column(String(300))
    overview: Mapped[str | None] = mapped_column(Text)
    genres: Mapped[list] = mapped_column(JSON, default=list)
    year: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[float | None] = mapped_column(Float)
    vote_count: Mapped[int] = mapped_column(Integer, default=0)
    poster_url: Mapped[str | None] = mapped_column(String(500))
    # Предобработанная строка признаков для TF-IDF
    feature_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ratings: Mapped[list["Rating"]] = relationship(back_populates="movie", lazy="selectin")
    watchlist: Mapped[list["Watchlist"]] = relationship(back_populates="movie", lazy="selectin") 