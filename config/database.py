"""database.py — подключение к БД через SQLAlchemy (синхронный режим).

За что отвечает модуль:
    • создаёт движок (engine) и фабрику сессий SQLAlchemy;
    • объявляет Base — общий предок всех ORM-моделей;
    • даёт зависимость get_db() для FastAPI, которая выдаёт сессию на один запрос
      и гарантированно её закрывает.

Почему синхронный SQLAlchemy, а не async:
    Приложение внутреннее и малонагруженное, данных немного. Синхронный код проще
    и понятнее, а FastAPI выполняет синхронные эндпоинты в пуле потоков, не блокируя
    сервер. Важный бонус: доменные порты (репозитории) остаются синхронными, поэтому
    доменный и прикладной слои не пришлось переписывать под async.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import get_settings

_settings = get_settings()

# Движок — точка подключения к PostgreSQL. pool_pre_ping проверяет «живость»
# соединения перед выдачей (защита от протухших коннектов).
engine = create_engine(_settings.database_url, pool_pre_ping=True, future=True)

# Фабрика сессий. expire_on_commit=False — объекты остаются доступными после commit
# (удобно, чтобы прочитать id только что сохранённой записи).
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей (SQLAlchemy 2.0 declarative)."""


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: открывает сессию на время запроса и закрывает после.

    Использование в эндпоинте:  db: Session = Depends(get_db).
    Конструкция try/finally гарантирует закрытие сессии даже при ошибке.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
