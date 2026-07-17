"""main.py — точка входа приложения FastAPI.

За что отвечает модуль:
    Собирает приложение: создаёт объект FastAPI, подключает CORS (доступ фронта),
    регистрирует обработчики доменных ошибок и роутеры (аутентификация, экраны),
    добавляет health-check. OpenAPI-документация доступна автоматически на /api/docs.

Запуск (dev):  uvicorn main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from core.api.errors import register_exception_handlers
from features.accounts.router import router as auth_router
from features.campaigns.presentation.router import router as campaigns_router
from features.cities.presentation.router import router as cities_router
from features.geo.router import router as geo_router
from features.landlords.presentation.router import router as landlords_router
from features.screen_types.presentation.router import router as screen_types_router
from features.screens.presentation.router import router as screens_router
from features.users.presentation.router import router as users_router


def create_app() -> FastAPI:
    """Создаёт и настраивает экземпляр приложения (фабрика приложения).

    Фабрика удобна для тестов: можно собрать отдельный экземпляр приложения.
    """
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/api/docs",       # Swagger UI
        openapi_url="/api/openapi.json",
    )

    # CORS: разрешаем запросы фронтенда (Flutter Web) с указанных адресов.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Перевод доменных ошибок в корректные HTTP-статусы.
    register_exception_handlers(app)

    # Маршруты модулей.
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(screens_router)
    app.include_router(landlords_router)
    app.include_router(campaigns_router)
    app.include_router(cities_router)
    app.include_router(screen_types_router)
    app.include_router(geo_router)

    # Файлы (фото/договоры) хранятся в объектном хранилище (S3/MinIO) и отдаются
    # клиенту напрямую по короткоживущим presigned-ссылкам — backend их не проксирует.

    @app.get("/api/health", tags=["Служебное"], summary="Проверка живости сервиса")
    def health() -> dict[str, str]:
        """Простой эндпоинт для мониторинга: отвечает, что сервис жив."""
        return {"status": "ok"}

    return app


# Экземпляр приложения, который запускает uvicorn (main:app).
app = create_app()
