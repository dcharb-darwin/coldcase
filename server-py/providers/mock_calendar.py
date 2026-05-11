"""Mock calendar provider with synthetic slot generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from providers.base import CalendarProvider


class MockCalendarProvider(CalendarProvider):
    """Generate deterministic availability options for demo use."""

    def get_availability(
        self,
        *,
        attendees: list[str],
        window_start: datetime,
        window_end: datetime,
    ) -> list[dict]:
        slots: list[dict] = []
        cursor = window_start.astimezone(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
        final = window_end.astimezone(UTC)

        while cursor < final and len(slots) < 3:
            if cursor.weekday() < 5:
                slots.append(
                    {
                        "start": cursor.isoformat(),
                        "end": (cursor + timedelta(minutes=45)).isoformat(),
                        "recommended": len(slots) == 0,
                        "attendees": attendees,
                    }
                )
            cursor += timedelta(days=1)
        return slots
