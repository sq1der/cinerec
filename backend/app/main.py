from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import time
from app.config import settings
from app.api.v1 import auth, movies, recommendations, users
from app.core.redis import get_redis, close_redis
from app.core.logging import setup_logging, get_logger
from app.services.recommendation.content_based import TFIDFModelData
from app.services.recommendation.collaborative import SVDModelData

setup_logging()
logger = get_logger("app.main")
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up CineRec API...")

    logger.info("Connecting to Redis...")
    await get_redis()
    logger.info("Redis connected")

    logger.info("Loading TF-IDF model...")
    t0 = time.perf_counter()
    app.state.tfidf_model = TFIDFModelData()
    logger.info(f"TF-IDF model loaded in {time.perf_counter() - t0:.2f}s — {len(app.state.tfidf_model.movie_ids)} movies")

    logger.info("Loading SVD model...")
    t0 = time.perf_counter()
    app.state.svd_model = SVDModelData()
    logger.info(f"SVD model loaded in {time.perf_counter() - t0:.2f}s — {len(app.state.svd_model.movie_ids)} items")

    logger.info("Application startup complete")
    yield

    logger.info("Shutting down...")
    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - t0) * 1000
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({duration:.1f}ms)"
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "message": "Validation error"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Internal server error"},
    )


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(movies.router, prefix="/api/v1/movies", tags=["movies"])
app.include_router(recommendations.router, prefix="/api/v1/recommendations", tags=["recommendations"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}