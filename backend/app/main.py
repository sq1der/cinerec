from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings 
from app.api.v1 import auth, movies, recommendations

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
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
# Роутеры подключим позже, когда напишем эндпоинты
# from app.api.v1 import auth, users, movies, recommendations
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])

@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}