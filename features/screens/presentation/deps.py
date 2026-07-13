"""deps.py — зависимости FastAPI для фичи «экраны».

За что отвечает модуль:
    Готовит объекты, которые нужны эндпоинтам, и внедряет их через Depends:
      • репозиторий экранов (с открытой на запрос сессией БД);
      • объектное хранилище файлов (S3/MinIO) — общий на процесс;
      • TTL presigned-ссылок из настроек;
      • текущего пользователя (из проверенного JWT-токена).

Так эндпоинты не создают зависимости сами — их собирает FastAPI (внедрение
зависимостей), что упрощает тестирование (зависимости легко подменить).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from config.settings import get_settings
from core.api.auth import get_current_user  # noqa: F401  (реэкспорт для удобства импорта)
from core.application.clock import SystemClock
from core.application.storage import FileStorage
from core.infrastructure.s3_storage import S3Config, S3FileStorage
from features.screens.application.expiry_sweep_guard import get_expiry_sweep_guard
from features.screens.application.use_cases.expire_due_screens import (
    ExpireDueScreensUseCase,
)
from features.screens.domain.repositories import ScreenRepository
from features.screens.infrastructure.repositories import SqlAlchemyScreenRepository


@lru_cache
def _build_file_storage() -> S3FileStorage:
    """Создаёт хранилище один раз на процесс (клиенты boto3 переиспользуются).

    Кэшируем, чтобы не создавать boto3-клиентов и не проверять бакет на каждый
    запрос — конфигурация хранилища на весь процесс одна.
    """
    settings = get_settings()
    return S3FileStorage(
        S3Config(
            bucket=settings.s3_bucket,
            internal_endpoint_url=settings.s3_internal_endpoint_url,
            public_endpoint_url=settings.s3_public_endpoint_url,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            region=settings.s3_region,
        )
    )


def get_file_storage() -> FileStorage:
    """Возвращает объектное хранилище файлов (S3/MinIO).

    Тип — интерфейс FileStorage: остальной код зависит от абстракции, а не от boto3 (DIP).
    """
    return _build_file_storage()


def get_presign_expiry() -> int:
    """TTL presigned-ссылок (секунды) из настроек — используется при сборке ответов."""
    return get_settings().s3_presign_expire_seconds


def get_screen_repository(db: Annotated[Session, Depends(get_db)]) -> ScreenRepository:
    """Возвращает репозиторий экранов, привязанный к сессии текущего запроса.

    Тип возвращаемого значения — интерфейс ScreenRepository (домен), а не
    конкретный класс: остальной код зависит от абстракции (DIP).
    """
    return SqlAlchemyScreenRepository(db)


def expire_due_screens(db: Annotated[Session, Depends(get_db)]) -> None:
    """Зависимость-триггер ленивой авто-архивации по истечению аренды (FR-4.4).

    Вешается на статус-зависимые READ-роуты (список/деталь экранов, дашборд,
    Excel, экраны арендодателя). Выполняется ДО тела эндпоинта в ТОЙ ЖЕ сессии
    Depends(get_db) (FastAPI кэширует её на запрос), поэтому:
      • когда sweep реально срабатывает, bulk-UPDATE виден последующим SELECT в
        той же транзакции → ответ фронту сразу содержит актуальные статусы;
      • дневной throttle (ExpirySweepGuard, синглтон на процесс) пропускает sweep,
        если сегодня уже подметали → в ~99% запросов это нулевая стоимость.

    Про commit: get_db в этом проекте лишь ЗАКРЫВАЕТ сессию (без commit), поэтому
    незакоммиченный bulk-UPDATE откатился бы при закрытии, и в следующие чтения дня
    (guard их пропускает) статусы «съехали» бы обратно на active. Поэтому фиксируем
    sweep ЯВНО — но только когда что-то реально заархивировано (n > 0), чтобы в
    подавляющем большинстве чтений не делать лишний commit. Отдельная транзакция на
    write-эндпоинтах не затрагивается: сюда зависимость не вешается.
    """
    clock = SystemClock()
    use_case = ExpireDueScreensUseCase(SqlAlchemyScreenRepository(db), clock)
    archived = get_expiry_sweep_guard().run_if_new_day(use_case, clock.today_bishkek())
    if archived:
        db.commit()
