"""Persons — case-scoped suspect / witness / victim / officer entries.

Phase B endpoints: list / create / update / delete, scoped to a case.
Phase C will add AI-extracted candidates plus PersonMention linking.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from models import Case, Person, PersonRole
from routers._deps import CurrentUser, current_user, require_perm
from services.vendor_scope import enforce_vendor_scope


router = APIRouter(
    tags=["Persons"],
    dependencies=[Depends(enforce_vendor_scope)],
)


class CreatePersonBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: PersonRole = PersonRole.OTHER
    descriptor: str = ""
    notes: str = ""


class UpdatePersonBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    role: Optional[PersonRole] = None
    descriptor: Optional[str] = None
    notes: Optional[str] = None


@router.get("/cases/{case_id}/persons")
@require_perm("case.read")
def list_persons(case_id: str, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    rows = Person.objects(tenant_id=user.tenant_id, case=case).order_by("role", "name")
    return {"persons": [p.to_dict() for p in rows]}


@router.post("/cases/{case_id}/persons", status_code=201)
@require_perm("case.edit")
def create_person(case_id: str, body: CreatePersonBody, user: CurrentUser = Depends(current_user)):
    case = Case.objects(id=case_id, tenant_id=user.tenant_id).first()
    if not case:
        raise HTTPException(404, "Case not found")
    p = Person(
        tenant_id=user.tenant_id, case=case,
        name=body.name.strip(),
        role=body.role.value,
        descriptor=body.descriptor.strip(),
        notes=body.notes.strip(),
        created_by=user.user_id,
    ).save()
    return p.to_dict()


@router.patch("/cases/{case_id}/persons/{person_id}")
@require_perm("case.edit")
def update_person(
    case_id: str, person_id: str, body: UpdatePersonBody,
    user: CurrentUser = Depends(current_user),
):
    p = Person.objects(id=person_id, tenant_id=user.tenant_id).first()
    if not p or str(p.case.id) != case_id:
        raise HTTPException(404, "Person not found")
    if body.name is not None:
        p.name = body.name.strip()
    if body.role is not None:
        p.role = body.role.value
    if body.descriptor is not None:
        p.descriptor = body.descriptor.strip()
    if body.notes is not None:
        p.notes = body.notes.strip()
    p.save()
    return p.to_dict()


@router.delete("/cases/{case_id}/persons/{person_id}", status_code=204)
@require_perm("case.edit")
def delete_person(case_id: str, person_id: str, user: CurrentUser = Depends(current_user)):
    p = Person.objects(id=person_id, tenant_id=user.tenant_id).first()
    if not p or str(p.case.id) != case_id:
        raise HTTPException(404, "Person not found")
    p.delete()
    return None
