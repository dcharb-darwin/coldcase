"""Mock evaluation provider backed by evaluation factor collection."""

from __future__ import annotations

from models import EvaluationFactor
from providers.base import EvaluationProvider


class MockEvaluationProvider(EvaluationProvider):
    """Return evaluation factors from seeded Mongo data."""

    def list_factors(self, *, class_code: str, department: str) -> list[dict]:
        query = EvaluationFactor.objects(position_class_code=class_code)
        scoped = query.filter(__raw__={"$or": [{"department": ""}, {"department": department}]})
        return [
            {
                "id": str(item.id),
                "position_class_code": item.position_class_code,
                "department": item.department,
                "factor_name": item.factor_name,
                "factor_code": item.factor_code,
            }
            for item in scoped
        ]
