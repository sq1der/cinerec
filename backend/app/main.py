from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.api.v1 import auth, movies, recommendations, users
from app.core.redis import get_redis, close_redis
from app.services.recommendation.content_based import TFIDFModelData
from app.services.recommendation.collaborative import SVDModelData

limiter = Limiter(key_func=get_remote_address)


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

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "message": "Validation error"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
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