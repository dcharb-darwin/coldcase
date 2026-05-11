"""Mock employee provider backed by Mongo seed data."""

from __future__ import annotations

from providers.base import EmployeeProvider
from models import Employee


class MockEmployeeProvider(EmployeeProvider):
    """Read employees from local MongoDB."""

    def list_employees(self) -> list[dict]:
        employees: list[dict] = []
        for employee in Employee.objects.order_by("-hire_date"):
            employees.append(
                {
                    "id": str(employee.id),
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "employee_id": employee.employee_id,
                    "position_title": employee.position_title,
                    "class_code": employee.class_code,
                    "department": employee.department,
                    "hire_date": employee.hire_date.isoformat(),
                    "work_schedule": employee.work_schedule,
                    "supervisor_name": employee.supervisor_name,
                    "supervisor_email": employee.supervisor_email,
                    "employee_email": employee.employee_email,
                    "photo_url": employee.photo_url,
                    "overall_status": employee.overall_status,
                }
            )
        return employees
