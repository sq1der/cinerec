from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings 
from app.api.v1 import auth, movies, recommendations, users
from app.core.redis import get_redis, close_redis
from app.services.recommendation.content_based import TFIDFModelData
from app.services.recommendation.collaborative import SVDModelData


class AppState:
    tfidf_model: TFIDFModelData
    svd_model: SVDModelData

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_redis()
    app.state.tfidf_model = TFIDFModelData()
    app.state.svd_model = SVDModelData()
    yield
    await close_redis()

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://ssndxz.github.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(movies.router, prefix="/api/v1/movies", tags=["movies"])
app.include_router(recommendations.router, prefix="/api/v1/recommendations", tags=["recommendations"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}