#!/bin/sh
set -e

# --- 1. Поднимаем сам сервер MinIO в фоне ---
minio server /data --console-address ":9001" &
MINIO_PID=$!

# --- 2. Ждём, пока MinIO начнёт отвечать на API-порту ---
echo "Ожидаем готовности MinIO..."
until curl -s -o /dev/null "http://localhost:9000/minio/health/live"; do
  sleep 1
done
echo "MinIO готов."

# --- 3. Настраиваем алиас mc и создаём бакет, если его ещё нет ---
mc alias set local http://localhost:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" >/dev/null

if ! mc ls "local/${BUCKET_NAME}" >/dev/null 2>&1; then
  echo "Создаём бакет: ${BUCKET_NAME}"
  mc mb "local/${BUCKET_NAME}"
else
  echo "Бакет ${BUCKET_NAME} уже существует."
fi

# --- 4. Возвращаем контейнер на передний план к процессу MinIO ---
wait "$MINIO_PID"
