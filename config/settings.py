"""settings.py — конфигурация приложения (замена Django settings).

За что отвечает модуль:
    Читает настройки из окружения/.env и предоставляет их как типизированный
    объект Settings. Благодаря pydantic-settings значения валидируются и имеют
    правильные типы (bool, int, список). Настройки берём один раз (кэшированно).

Почему так (12-factor): конфигурация отделена от кода и приходит из окружения —
одно и то же приложение работает в dev и prod с разными .env.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки приложения в одном месте (валидируются pydantic)."""

    # Загружаем из файла .env; лишние переменные окружения игнорируем.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Общее ---
    app_name: str = "LED Dashboard KG API"
    debug: bool = False

    # --- Безопасность / JWT ---
    secret_key: str = "unsafe-dev-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # --- База данных ---
    database_url: str = "postgresql+psycopg://led:led@localhost:5432/led_dashboard"

    # --- CORS (адреса фронтенда) ---
    # Храним как СЫРУЮ строку "a,b,c", а не list[str]: pydantic-settings пытается
    # разобрать значения env-переменных для «сложных» типов (list, dict, ...) как
    # JSON, и на строке через запятую падает с ошибкой ещё до того, как отработают
    # обычные валидаторы модели. Для типа str такой JSON-декодинг не запускается —
    # это единственный надёжный способ принять список из .env через запятую.
    # Список для использования в коде — через property cors_origins ниже.
    cors_origins_raw: str = Field(default="", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        """Адреса фронтенда для CORS, разобранные из CORS_ORIGINS ("a,b,c" → список).

        Пустые элементы (лишние запятые/пробелы в .env) отбрасываются.
        """
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    # --- Демо-учётка (историческая; вход теперь идёт по таблице users) ---
    # Оставлены для обратной совместимости .env; на аутентификацию больше не влияют.
    superuser_username: str = "admin"
    superuser_password: str = "admin12345"

    # --- Bootstrap-админ (сид users, чтобы после миграции был ≥1 администратор) ---
    # Идемпотентный upsert в миграции 0007: если пользователя нет — создаётся с
    # role=admin; если есть — промоутится до admin. Дефолты совпадают с прежней
    # демо-учёткой (admin/admin12345), поэтому существующий вход продолжает работать.
    initial_admin_username: str = Field(default="admin", alias="INITIAL_ADMIN_USERNAME")
    initial_admin_password: str = Field(default="admin12345", alias="INITIAL_ADMIN_PASSWORD")

    # --- Объектное хранилище файлов (S3/MinIO) для фото и договоров ---
    # Внутренний адрес — из сети backend (put/delete); публичный — тот, до которого
    # дотягивается браузер/устройство (под ним подписывается presigned-ссылка).
    # Значения по умолчанию рассчитаны на docker-compose (сервис minio).
    s3_bucket: str = "led-attachments"
    s3_internal_endpoint_url: str = "http://minio:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minio"
    s3_secret_key: str = "minio12345"
    s3_region: str = "us-east-1"
    s3_presign_expire_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    """Возвращает единственный экземпляр настроек (кэшируется на весь процесс).

    lru_cache гарантирует, что .env читается один раз, а не при каждом обращении.
    """
    return Settings()
