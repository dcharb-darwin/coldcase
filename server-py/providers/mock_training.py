"""Mock training provider backed by training requirements collection."""

from __future__ import annotations

from models import TrainingRequirement
from providers.base import TrainingProvider


class MockTrainingProvider(TrainingProvider):
    """Return training requirements from seeded Mongo data."""

    def list_requirements(self, *, class_code: str, department: str) -> list[dict]:
        query = TrainingRequirement.objects(position_class_code=class_code)
        scoped = query.filter(__raw__={"$or": [{"department": ""}, {"department": department}]})
        return [
            {
                "id": str(item.id),
                "position_class_code": item.position_class_code,
                "department": item.department,
                "training_name": item.training_name,
                "completion_window_days": item.completion_window_days,
                "mandatory": item.mandatory,
            }
            for item in scoped
        ]
