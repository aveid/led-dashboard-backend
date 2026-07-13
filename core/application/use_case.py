"""use_case.py — базовый класс прикладного слоя (Use Case / Interactor).

Что такое use case:
    Один сценарий работы системы = один класс (например, «создать экран»,
    «посчитать стоимость выбранных экранов»). Он оркеструет домен и репозитории,
    но сам не содержит деталей БД или HTTP.

Зачем базовый класс:
    Задаёт единый контракт `execute(input) -> output` для всех сценариев.
    Благодаря этому:
      • слой представления вызывает любой use case одинаково;
      • каждый use case отвечает ровно за один сценарий (принцип SRP);
      • сценарии легко тестировать в изоляции (подставив фейковые репозитории).

Типы Input/Output — обобщённые (Generic), чтобы у каждого сценария были свои.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

# Input  — тип входных данных сценария (обычно DTO-запрос).
# Output — тип результата сценария (сущность, DTO-ответ и т.п.).
Input = TypeVar("Input")
Output = TypeVar("Output")


class UseCase(ABC, Generic[Input, Output]):
    """Базовый сценарий приложения. Наследники реализуют метод execute()."""

    @abstractmethod
    def execute(self, data: Input) -> Output:
        """Выполнить сценарий: принять входные данные, вернуть результат.

        Наследник кладёт сюда бизнес-логику сценария. При нарушении правил
        выбрасывает доменные исключения (см. core/domain/exceptions.py).
        """
        raise NotImplementedError

    def __call__(self, data: Input) -> Output:
        """Позволяет вызывать сценарий как функцию: use_case(data)."""
        return self.execute(data)
