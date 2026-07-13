"""add_attachment.py — сценарий «Загрузить файл к экрану» (FR-3.12/3.13).

За что отвечает: принимает сырой файл, проверяет его (тип/размер), кладёт в
объектное хранилище под уникальным внутренним ключом (object_key) и создаёт запись
вложения у экрана. Генерация ссылки на скачивание здесь НЕ делается — её собирает
слой представления из object_key через порт FileStorage при чтении экрана.

Порядок шагов (по инструкции Архитектора):
    1. Проверить MIME-тип: content_type ∈ ALLOWED_MIME[kind]  (иначе 415).
    2. Проверить размер: len(data) ≤ MAX_SIZE_BYTES[kind]     (иначе 413).
    3. Проверить существование экрана                          (иначе 404).
    4. Проверить лимит вложений вида (MAX_ATTACHMENTS_PER_KIND) ДО put (иначе 409).
    5. Сгенерировать object_key = screens/<id>/<kind>/<uuid><ext>.
    6. Положить файл в хранилище (storage.put).
    7. Добавить вложение к экрану и сохранить.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.application.storage import FileStorage
from core.application.use_case import UseCase
from core.domain.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError
from features.screens.application.dto import AddAttachmentInput
from features.screens.application.object_key import build_object_key
from features.screens.domain.attachment_policy import (
    MAX_ATTACHMENTS_PER_KIND,
    AttachmentLimitExceededError,
)
from features.screens.domain.entities import Attachment, Screen
from features.screens.domain.enums import AttachmentType
from features.screens.domain.repositories import ScreenRepository

# MIME-типы картинок и документов. Фото — только картинки; договор/прочий
# документ — PDF, скан-картинка или Word (.doc/.docx).
_IMAGE_MIME = frozenset({"image/jpeg", "image/png", "image/webp"})
_DOCUMENT_MIME = frozenset(
    {
        "application/pdf",
        "application/msword",  # .doc
        # .docx
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

# Разрешённые MIME-типы по типу вложения (allowlist).
ALLOWED_MIME: dict[AttachmentType, frozenset[str]] = {
    AttachmentType.PHOTO: _IMAGE_MIME,
    AttachmentType.CONTRACT: _IMAGE_MIME | _DOCUMENT_MIME,
    AttachmentType.OTHER: _IMAGE_MIME | _DOCUMENT_MIME,
}

# Fallback «расширение → канонический MIME». Нужен, когда браузер/клиент прислал
# generic content_type (application/octet-stream или пусто) — для .doc/.docx это
# частый случай, из-за которого корректный файл иначе резался бы 415.
EXT_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Content-type'ы, которым нельзя доверять: разрешаем уточнить их по расширению файла.
_GENERIC_CONTENT_TYPES = frozenset({"", "application/octet-stream"})

# Максимальный размер файла (в байтах) по типу вложения.
MAX_SIZE_BYTES: dict[AttachmentType, int] = {
    AttachmentType.PHOTO: 10 * 1024 * 1024,     # 10 MB
    AttachmentType.CONTRACT: 25 * 1024 * 1024,  # 25 MB
    AttachmentType.OTHER: 25 * 1024 * 1024,     # 25 MB
}


class AddAttachmentUseCase(UseCase[AddAttachmentInput, Screen]):
    """Проверяет файл, кладёт его в хранилище и прикрепляет вложение к экрану."""

    def __init__(self, repository: ScreenRepository, storage: FileStorage) -> None:
        """Внедряем репозиторий и хранилище через конструктор (DIP)."""
        self._repository = repository
        self._storage = storage

    def execute(self, data: AddAttachmentInput) -> Screen:
        """Валидировать → сохранить в хранилище → создать вложение → сохранить экран."""
        kind = data.attachment_type
        ext = Path(data.filename).suffix.lower()

        # Если клиент прислал generic content_type (octet-stream/пусто) — уточняем
        # его по расширению файла, чтобы корректный .doc/.docx не резался 415.
        content_type = data.content_type
        if content_type in _GENERIC_CONTENT_TYPES:
            content_type = EXT_TO_MIME.get(ext, content_type)

        if content_type not in ALLOWED_MIME[kind]:
            raise UnsupportedMediaTypeError(
                f"Тип файла '{content_type}' не разрешён для вложения '{kind.value}'."
            )
        if len(data.data) > MAX_SIZE_BYTES[kind]:
            raise PayloadTooLargeError(
                f"Файл превышает допустимый размер для '{kind.value}' "
                f"({MAX_SIZE_BYTES[kind]} байт)."
            )

        # Существование экрана: get_by_id бросит NotFoundError (→ 404), если его нет.
        screen = self._repository.get_by_id(data.screen_id)

        # Лимит вложений данного вида (SSOT числа — MAX_ATTACHMENTS_PER_KIND в домене).
        # Проверяем ДО обращения к хранилищу: иначе при отказе по лимиту в MinIO
        # останется «сирота» (объект без записи в БД и без presigned-ссылки).
        if (
            self._repository.count_attachments_by_type(data.screen_id, kind)
            >= MAX_ATTACHMENTS_PER_KIND
        ):
            raise AttachmentLimitExceededError(kind, MAX_ATTACHMENTS_PER_KIND)

        # Единый билдер ключа: имя человека в ключ не кладём (uuid+ext), инвариант
        # «без ведущего слэша» гарантирован билдером. object_key сохраняется в БД и
        # тем же значением подписывается при presign — upload и presign используют один ключ.
        object_key = build_object_key(data.screen_id, kind.value, f"{uuid4().hex}{ext}")
        self._storage.put(object_key, data.data, content_type)

        attachment = Attachment(
            type=kind,
            object_key=object_key,
            original_filename=data.filename,
            content_type=content_type,
            size_bytes=len(data.data),
            uploaded_at=datetime.now(UTC),
        )
        screen.add_attachment(attachment)

        return self._repository.update(screen)
