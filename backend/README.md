# CineRec API

Бэкенд для платформы рекомендаций фильмов и сериалов.  
Дипломная работа — FastAPI + PostgreSQL + гибридная система рекомендаций.

## Технологии

- **FastAPI** — REST API
- **SQLAlchemy 2.0** (async) + **PostgreSQL** — база данных
- **Alembic** — миграции
- **Redis** — кэширование токенов
- **scikit-learn / scipy** — система рекомендаций (TF-IDF + SVD)
- **JWT** — аутентификация

## Архитектура системы рекомендаций

| Алгоритм | Метод | Когда используется |
|---|---|---|
| Content-Based | TF-IDF + cosine similarity | Похожие фильмы, < 20 оценок |
| Collaborative | SVD (matrix factorization) | > 20 оценок |
| Hybrid | Взвешенное объединение | Персональные рекомендации |
| Trending | Рейтинг + популярность | Cold start (< 5 оценок) |

## Быстрый старт

### С Docker (рекомендуется)
```bash
git clone <repo>
cd cinerec/backend

# Запуск всех сервисов
docker compose up -d

# Применить миграции
docker compose exec api alembic upgrade head

# Загрузить тестовые данные (нужен TMDB API ключ)
docker compose exec api python scripts/seed_movies.py
```

### Локально
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Запустить PostgreSQL и Redis
docker compose up postgres redis -d

# Создать .env (см. .env.example)
cp .env.example .env

# Миграции
alembic upgrade head

# Сервер
uvicorn app.main:app --reload --port 8000
```

## API документация

После запуска открой в браузере:

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Основные эндпоинты
```
POST /api/v1/auth/register     — регистрация
POST /api/v1/auth/login        — логин, получение JWT
POST /api/v1/auth/refresh      — обновление токена
GET  /api/v1/auth/me           — текущий пользователь

GET  /api/v1/movies/           — каталог с фильтрами
GET  /api/v1/movies/search     — поиск
POST /api/v1/movies/{id}/rate  — поставить оценку
POST /api/v1/movies/{id}/watchlist — добавить в список

GET  /api/v1/recommendations/personal  — персональные
GET  /api/v1/recommendations/similar/{id} — похожие
GET  /api/v1/recommendations/trending  — популярное
```

## Тесты
```bash
pytest -v                          # все тесты
pytest tests/test_auth.py -v       # только auth
pytest --cov=app --cov-report=term-missing  # с покрытием
```

## Структура проекта
```
backend/
├── app/
│   ├── api/v1/          # эндпоинты
│   ├── core/            # security, dependencies
│   ├── models/          # SQLAlchemy модели
│   ├── repositories/    # работа с БД
│   ├── schemas/         # Pydantic схемы
│   └── services/
│       └── recommendation/
│           ├── content_based.py  # TF-IDF
│           ├── collaborative.py  # SVD
│           └── hybrid.py         # объединение
├── alembic/             # миграции
├── tests/               # pytest
├── Dockerfile
└── docker-compose.yml
```