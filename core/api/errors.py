"""errors.py — перевод доменных исключений в HTTP-ответы (для FastAPI).

За что отвечает модуль:
    Регистрирует на приложении FastAPI обработчики, которые ловят доменные
    исключения и превращают их в аккуратные JSON-ответы с нужным статусом:
        ValidationError            → 400 Bad Request
        BusinessRuleViolation      → 409 Conflict
        NotFoundError              → 404 Not Found
        UnprocessableEntityError   → 422 Unprocessable Entity
        UnsupportedMediaTypeError  → 415 Unsupported Media Type
        PayloadTooLargeError       → 413 Payload Too Large
    Формат тела — FastAPI-стиль: {"detail": "<человекочитаемое сообщение>"} (единый
    для всего приложения, backend-instruction §7). Так доменные ошибки читаются
    фронтом тем же путём, что и штатные ошибки FastAPI (Pydantic-422 отдаёт
    detail-список, HTTPException — detail-строку/объект).

Почему централизованно:
    Домен и use cases просто выбрасывают исключения, не зная про HTTP. Всё
    сопоставление «ошибка → статус» собрано здесь (принцип DRY и разделение слоёв).
"""


from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.domain.exceptions import (
    BusinessRuleViolation,
    NotFoundError,
    PayloadTooLargeError,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
    ValidationError,
)

# Сопоставление типа доменной ошибки → HTTP-статус.
_STATUS_BY_EXCEPTION: dict[type[Exception], int] = {
    ValidationError: 400,
    BusinessRuleViolation: 409,
    NotFoundError: 404,
    UnprocessableEntityError: 422,
    UnsupportedMediaTypeError: 415,
    PayloadTooLargeError: 413,
}


def _make_response(exc: Exception, status_code: int) -> JSONResponse:
    """Формирует единообразный JSON-ответ об ошибке в FastAPI-стиле (§7).

    Тело — {"detail": "<сообщение>"}: тот же ключ detail, что у штатных ошибок
    FastAPI, поэтому фронт показывает сообщение единым способом.
    """
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    """Подключает обработчики доменных ошибок к приложению (вызывается в main.py).

    Для каждого типа доменной ошибки регистрируем обработчик, который отдаёт
    правильный статус. Так ни одна доменная ошибка не «утечёт» как 500.
    """
    for exc_type, status_code in _STATUS_BY_EXCEPTION.items():
        # Замыкание с параметром по умолчанию фиксирует текущий status_code.
        async def handler(_: Request, exc: Exception, code: int = status_code) -> JSONResponse:
            return _make_response(exc, code)

        app.add_exception_handler(exc_type, handler)
