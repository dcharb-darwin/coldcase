"""
Provider interfaces — every external system goes through one of these.
Selection is env-driven (PROVIDER_* in config.py). See docs/PATTERNS.md §1.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class EmployeeProvider(ABC):
    @abstractmethod
    def get_employee(self, employee_id: str) -> dict | None: ...
    @abstractmethod
    def list_employees(self) -> list[dict]: ...


class EmailProvider(ABC):
    @abstractmethod
    def send_email(self, *, to: str, subject: str, body_html: str) -> dict: ...
    @abstractmethod
    def get_email_log(self, employee_id: str | None = None) -> list[dict]: ...


class CalendarProvider(ABC):
    @abstractmethod
    def get_availability(
        self,
        *,
        attendees: list[str],
        window_start: datetime,
        window_end: datetime,
    ) -> list[dict]: ...

    @abstractmethod
    def create_event(self, *, attendees: list[str], start: datetime, end: datetime, subject: str) -> dict: ...


class TrainingProvider(ABC):
    @abstractmethod
    def get_assignments(self, employee_id: str) -> list[dict]: ...
    @abstractmethod
    def get_completion_status(self, employee_id: str) -> dict: ...


class EvaluationProvider(ABC):
    @abstractmethod
    def get_factors(self, position_code: str) -> list[dict]: ...
    @abstractmethod
    def get_submission_status(self, employee_id: str) -> dict: ...


class PhotoProvider(ABC):
    @abstractmethod
    def get_photo(self, employee_id: str) -> str | None:
        """Return a URL or data URI for the photo, or None if absent."""
