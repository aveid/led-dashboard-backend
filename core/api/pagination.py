"""pagination.py — простая пагинация списков (limit/offset) для FastAPI.

За что отвечает: даёт единый способ ограничивать размер выборки в списочных
эндпоинтах, чтобы ответы были предсказуемыми и не «падали» на больших данных.
Используется как зависимость:  params: PaginationParams = Depends().

Для MVP этого достаточно; при необходимости позже добавим общий конверт ответа
с total/страницами.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query


@dataclass
class PaginationParams:
    """Параметры постраничной выдачи, приходящие из query-строки запроса.

    limit  — сколько записей вернуть (1..200, по умолчанию 50);
    offset — сколько записей пропустить от начала (для «следующей страницы»).
    """

    limit: int = Query(50, ge=1, le=200, description="Сколько записей вернуть")
    offset: int = Query(0, ge=0, description="Сколько записей пропустить")
