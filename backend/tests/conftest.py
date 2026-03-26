import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.core.security import hash_password
from app.models.user import User
from app.models.movie import Movie
from app.models.rating import Rating, Watchlist  # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Создаём таблицы один раз на всю сессию."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """Очищаем все таблицы перед каждым тестом."""
    yield
    async with test_engine.begin() as conn:
        # Порядок важен — сначала дочерние таблицы
        await conn.run_sync(
            lambda c: [
                c.execute(Base.metadata.tables[t].delete())
                for t in ["watchlist", "ratings", "movies", "users"]
                if t in Base.metadata.tables
            ]
        )


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> User:
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("password123"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    resp = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_movies(db: AsyncSession) -> list[Movie]:
    movies = [
        Movie(
            id=1,
            title="Inception",
            original_title="Inception",
            overview="A thief who steals corporate secrets through dream-sharing technology.",
            genres=["Action", "Sci-Fi"],
            year=2010,
            rating=8.8,
            vote_count=2000000,
            feature_text="Inception Action Sci-Fi dream-sharing technology thief",
        ),
        Movie(
            id=2,
            title="The Matrix",
            original_title="The Matrix",
            overview="A computer hacker learns about the true nature of reality.",
            genres=["Action", "Sci-Fi"],
            year=1999,
            rating=8.7,
            vote_count=1800000,
            feature_text="The Matrix Action Sci-Fi computer hacker reality simulation",
        ),
        Movie(
            id=3,
            title="Interstellar",
            original_title="Interstellar",
            overview="A team of explorers travel through a wormhole in space.",
            genres=["Sci-Fi", "Drama"],
            year=2014,
            rating=8.6,
            vote_count=1600000,
            feature_text="Interstellar Sci-Fi Drama space wormhole explorers",
        ),
    ]
    for m in movies:
        db.add(m)
    await db.commit()
    return movies