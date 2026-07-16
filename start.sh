#!/bin/bash
# Применяем миграции БД
alembic upgrade head

# Запускаем сервер
# Примечание: --reload полезен для отладки на тесте
uvicorn main:app --host=0.0.0.0 --port=8000 --reload


# alembic upgrade head && uvicorn main:app --host=0.0.0.0 --port=8000 --reload
