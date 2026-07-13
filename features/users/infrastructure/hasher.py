"""hasher.py — адаптер порта PasswordHasher поверх существующего auth-хешера.

Переиспользует config.security.hash_password (bcrypt/passlib) — второй хешер не
заводим (инструкция §2.5). Тонкая обёртка, приводящая функцию к порту
PasswordHasher, чтобы прикладные сценарии зависели от интерфейса, а не от config.
"""

from __future__ import annotations

from config.security import hash_password


class PasslibPasswordHasher:
    """Реализация PasswordHasher поверх bcrypt-хешера из config.security."""

    def hash(self, plain_password: str) -> str:
        """Возвращает bcrypt-хеш пароля (тот же алгоритм, что и при логине)."""
        return hash_password(plain_password)
