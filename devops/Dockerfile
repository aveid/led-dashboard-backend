# Используем ваш приватный registry
FROM registry.megacom.kg/docker/library/python:3.12-slim

# Настраиваем прокси для скачивания пакетов и переменные Python
ENV http_proxy=http://10.231.245.243:3128 \
    https_proxy=http://10.231.245.243:3128 \
    HTTP_PROXY=http://10.231.245.243:3128 \
    HTTPS_PROXY=http://10.231.245.243:3128 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir .

RUN mkdir -p /app/media

EXPOSE 8000

CMD ["sh", "-c", ". /vault/secrets/env && alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
#CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]



# # =============================================================================
# # Dockerfile — образ backend-сервиса (FastAPI).
# #
# # За что отвечает:
# #   Собирает контейнер с приложением: ставит зависимости, копирует исходники,
# #   при старте применяет миграции БД и поднимает uvicorn. Рассчитан на
# #   docker-compose (см. docker-compose.yml) — сам по себе, без БД рядом, работать
# #   не будет (нужен сервис db).
# #
# # Один образ на весь бэкенд: фронтенд (Flutter Web) будет собираться отдельным
# # образом/контейнером — они не смешиваются.
# # =============================================================================

# FROM python:3.12-slim

# # PYTHONDONTWRITEBYTECODE — не писать .pyc (не нужны в контейнере, короткоживущем).
# # PYTHONUNBUFFERED — логи Python сразу попадают в `docker logs`, без буферизации.
# ENV PYTHONDONTWRITEBYTECODE=1 \
#     PYTHONUNBUFFERED=1

# WORKDIR /app

# # curl нужен только для healthcheck (см. docker-compose.yml).
# # psycopg[binary] и shapely ставятся из готовых wheel-колёс (бинарники libpq/geos
# # уже внутри), поэтому gcc/libpq-dev/libgeos-dev здесь не нужны — образ легче.
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends curl \
#     && rm -rf /var/lib/apt/lists/*

# # Копируем весь код и ставим зависимости проекта (runtime, без dev-инструментов —
# # линт/тесты гоняем локально/в CI, не в образе). pip install . читает pyproject.toml
# # и ставит и зависимости, и сам проект (нужно для корректного резолва пакетов).
# COPY . .
# RUN pip install --no-cache-dir .

# # Каталог для локально сохранённых файлов (фото/договоры), см. config/settings.py
# # media_root. В compose монтируется как volume, чтобы данные переживали пересборку.
# RUN mkdir -p /app/media

# EXPOSE 8000

# # Перед стартом сервера применяем миграции — удобно для разработки (одна команда
# # `docker compose up` поднимает и БД, и актуальную схему, и сервер). Для прод-режима
# # с несколькими репликами миграции лучше выносить в отдельный шаг деплоя, но для
# # внутреннего дашборда с одним инстансом это не проблема.
# CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
