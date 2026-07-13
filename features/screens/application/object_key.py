"""object_key.py — единый билдер ключа объекта хранилища для вложений.

Инвариант: object_key НИКОГДА не начинается со слэша. Ведущий '/' в S3/MinIO
даёт ДРУГОЙ ключ ('/media/...' != 'media/...'): presigned-URL подпишется валидно,
но объекта по этому ключу нет → NoSuchKey при открытии вложения. Единая точка
сборки ключа гарантирует, что ключ, под которым файл КЛАДЁТСЯ и который сохраняется
в БД (а затем подписывается при presign), всегда нормализован.

Структура ключа: screens/<screen_id>/<kind>/<unique_filename>.
Имя человека в ключ НЕ кладём (оно хранится отдельно в Attachment.original_filename)
— так снимается проблема санитайзера имени; в ключе только uuid + расширение.
"""

from __future__ import annotations

import posixpath

# Корневой префикс всех вложений экранов в бакете.
MEDIA_PREFIX = "screens"


def build_object_key(screen_id: str | int, kind: str, unique_filename: str) -> str:
    """Собирает нормализованный object_key вложения.

    screen_id       — id экрана (сегмент пути);
    kind            — тип вложения (photo/contract/other), сегмент пути;
    unique_filename — уникальное имя объекта (uuid + расширение), без имени человека.

    Возвращает ключ БЕЗ ведущего слэша (инвариант хранилища).
    """
    key = posixpath.join(MEDIA_PREFIX, str(screen_id), kind, unique_filename)
    return key.lstrip("/")
