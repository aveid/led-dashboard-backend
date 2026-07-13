"""s3_storage.py — реализация FileStorage поверх S3/MinIO (boto3).

За что отвечает модуль:
    Хранит файлы (фото экранов, сканы договоров) в S3-совместимом хранилище
    (в dev — MinIO из docker-compose) и выдаёт короткоживущие presigned-ссылки на
    скачивание. Это «прод-грейд» замена локального диска: закрывает инфраструктурный
    долг S3FileStorage, оставляя контракт FileStorage прежним (DIP).

Ключевая тонкость (Docker/сеть):
    Адрес, по которому backend КЛАДЁТ/удаляет объекты (internal_endpoint_url,
    напр. http://minio:9000 внутри сети compose), почти всегда НЕ совпадает с
    адресом, до которого дотягивается браузер/устройство клиента
    (public_endpoint_url, напр. http://localhost:9000 в dev или https://cdn.<domain>
    в prod). Presigned-подпись включает host, поэтому ссылки для клиента надо
    генерировать ОТДЕЛЬНЫМ клиентом, настроенным на публичный адрес.
"""

from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from core.application.storage import FileStorage


@dataclass(frozen=True)
class S3Config:
    """Параметры подключения к объектному хранилищу (собираются из настроек)."""

    bucket: str
    internal_endpoint_url: str   # адрес хранилища из сети backend (put/delete)
    public_endpoint_url: str     # адрес хранилища, доступный клиенту (presign)
    access_key: str
    secret_key: str
    region: str = "us-east-1"


class S3FileStorage(FileStorage):
    """Хранилище файлов в S3/MinIO: put/delete по внутреннему адресу, presign — по публичному."""

    def __init__(self, cfg: S3Config) -> None:
        """Создаёт два клиента (внутренний и публичный) и гарантирует наличие бакета."""
        self._bucket = cfg.bucket
        # Path-style адресация (Key в пути, а не в поддомене) — так надёжнее с MinIO
        # и с произвольными LAN-адресами, где virtual-host стиль недоступен.
        client_cfg = Config(signature_version="s3v4", s3={"addressing_style": "path"})

        # Клиент для put/delete — внутренний адрес хранилища (docker network).
        self._io = boto3.client(
            "s3",
            endpoint_url=cfg.internal_endpoint_url,
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key,
            region_name=cfg.region,
            config=client_cfg,
        )
        # Отдельный клиент для presign — ПУБЛИЧНЫЙ адрес, доступный клиенту/устройству.
        self._presign = boto3.client(
            "s3",
            endpoint_url=cfg.public_endpoint_url,
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key,
            region_name=cfg.region,
            config=client_cfg,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Создаёт бакет, если его ещё нет (идемпотентно, вызывается один раз при старте)."""
        try:
            self._io.head_bucket(Bucket=self._bucket)
        except ClientError:
            # head_bucket бросает 404/403, если бакета нет — создаём его.
            self._io.create_bucket(Bucket=self._bucket)

    @staticmethod
    def _require_normalized_key(object_key: str) -> None:
        """Guard инварианта хранилища: object_key не начинается со слэша.

        Ведущий '/' в S3/MinIO даёт ДРУГОЙ ключ ('/media/...' != 'media/...'):
        presigned-URL подпишется валидно, но объекта по нему нет → NoSuchKey.
        Ловим регресс на границе хранилища, а не после жалобы пользователя.
        """
        if object_key.startswith("/"):
            raise ValueError(
                f"object_key не должен начинаться со слэша: {object_key!r} "
                "(ведущий '/' ломает адресацию в S3/MinIO → NoSuchKey)."
            )

    def put(self, object_key: str, data: bytes, content_type: str) -> None:
        """Кладёт объект в бакет по ключу с указанным Content-Type."""
        self._require_normalized_key(object_key)
        self._io.put_object(
            Bucket=self._bucket, Key=object_key, Body=data, ContentType=content_type
        )

    def generate_presigned_get_url(self, object_key: str, expires_in: int) -> str:
        """Возвращает presigned GET-ссылку под публичным адресом хранилища."""
        self._require_normalized_key(object_key)
        return self._presign.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )

    def delete(self, object_key: str) -> None:
        """Удаляет объект из бакета (S3 delete_object идемпотентен)."""
        self._require_normalized_key(object_key)
        self._io.delete_object(Bucket=self._bucket, Key=object_key)
