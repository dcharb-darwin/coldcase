# Role Library

> Proven manifests from shipped Launchpad apps. Find the closest shape to your app; copy as a starting point; evolve per [`ROLES.md`](ROLES.md). Domain-specific nouns anonymized or kept based on whether the noun is transferable.

## How to use this library

1. Skim the **shape table** below. Match your app to the closest pattern.
2. Open that app's section. Read the role list + the "why each role exists" commentary.
3. Copy the role + permission structure (not the domain nouns) into your Stage 1 manifest.
4. Add to `docs/role-evolution.md`: "Stage 1 baseline derived from `<source-app>` pattern."

## Shape table

| App | Domain | Perms | Roles | Scope types | Key pattern |
|---|---|---|---|---|---|
| **SOP Builder** | Document library with owner partitioning | 15 | 6 | `owner_group` + `sop` | HR/IT-pattern — scoped editor + unscoped reader together |
| **Crew Scheduler** | Multi-station rostering with battalion hierarchy | 19 | 7 | `station` + `battalion` | Two-tier scope (station inside battalion) + cross-reader |
| **HR Coordinator** | Per-person onboarding workflow | 17 | 6 | `department` + `employee` | Person-scoped liaison role + department manager |
| **Redactit / Doc Redaction** | Matter-scoped document review pipeline | 16 | 6 | `matter` + `document` | Reviewer / releaser / requester split (pipeline roles) |

All 5 apps share: `admin` (locked, `["*"]`), one fully-capable editor role, one read-only role. The variation is scoping + intermediate roles.

---

## SOP Builder — document library pattern

**Use when:** your app has a collection of documents / artifacts partitioned by some "owner" (library, workspace, team). Users need to edit within their partition; some users need to read across all partitions.

```python
permissions = {
    # Core resource
    "sop.read": ...,           # view SOPs and metadata
    "sop.create": ...,         # upload/create
    "sop.edit_own": ...,       # modify SOPs they authored
    "sop.edit_any": ...,       # modify any SOP
    "sop.accept": ...,         # terminal action (lock)
    "sop.upload": ...,         # upload supporting files
    "sop.publish": ...,        # make public
    "sop.find_by_task": ...,   # AI-assisted search
    "view.cross_library": ...,  # see SOPs outside your own library
    "tags.manage": ...,
    "admin.view": ...,
    "roles.manage": ...,
}

seed_roles = {
    "admin": ["*"],                        # locked, unlimited
    "library_editor": [                    # scoped to an owner_group
        "sop.read", "sop.create", "sop.edit_any",
        "sop.accept", "sop.upload", "sop.publish",
        "sop.find_by_task", "tags.manage",
    ],
    "cross_library_reader": [              # tenant-wide read
        "sop.read", "view.cross_library", "sop.find_by_task",
    ],
    "creator": [                           # any library, own SOPs
        "sop.read", "sop.create", "sop.edit_own",
        "sop.upload", "sop.find_by_task", "tags.manage",
    ],
    "reviewer": [                          # read + accept, scoped
        "sop.read", "sop.accept", "sop.find_by_task",
    ],
    "reader": [                            # scoped to library or SOP
        "sop.read", "sop.find_by_task",
    ],
}

scope_types = [
    ScopeType(id="owner_group", label="Library", list_endpoint="..."),
    ScopeType(id="sop", label="SOP", list_endpoint="..."),
]
```

### Why the roles

- `library_editor` is **scoped** — you assign it with a specific library id. One user gets `library_editor(HR)` and `library_editor(IT)` as two assignments.
- `cross_library_reader` is **tenant-wide** — pair with `library_editor(HR)` to get the HR pattern ("sees everything, edits only HR").
- `creator` is for IC contributors who own their own work without department ties.
- `reviewer` is for QA/compliance personas — scoped to whatever they review.
- `reader` is the small-blast-radius external role.

### When to start here

Your app ships documents, artifacts, or records that someone owns. Users want to see across ownership boundaries without being able to edit everywhere.

---

## Crew Scheduler — multi-station pattern

**Use when:** your app has nested physical/organizational hierarchy (battalion > station > crew), and users need roles at different hierarchy levels.

```python
seed_roles = {
    "admin": ["*"],
    "scheduler": [                         # builds schedules tenant-wide
        "schedule.read", "schedule.create", "schedule.edit",
        "schedule.publish", "shift.swap", "personnel.read",
    ],
    "station_editor": [                    # scoped to one station
        "schedule.read", "schedule.edit",
        "shift.read", "shift.swap", "personnel.read",
    ],
    "battalion_editor": [                  # scoped to one battalion
        "schedule.read", "schedule.edit", "schedule.publish",
        "shift.read", "shift.swap", "personnel.read", "view.cross_station",
    ],
    "cross_station_reader": [              # tenant-wide read
        "schedule.read", "view.cross_station", "personnel.read",
    ],
    "reader": ["schedule.read", "personnel.read"],
    "auditor": [                           # read everything + audit log
        "schedule.read", "view.cross_station", "personnel.read", "audit.read",
    ],
}

scope_types = [
    ScopeType(id="station", label="Station", list_endpoint="..."),
    ScopeType(id="battalion", label="Battalion", list_endpoint="..."),
]
```

### Why the roles

- `station_editor` and `battalion_editor` are the same pattern — one scoped to a leaf, one scoped to the parent. The battalion editor also gets `view.cross_station` so they can see all stations in their battalion.
- `cross_station_reader` is the same "HR pattern" as SOP — pair with a scoped editor for see-all-edit-one.
- `auditor` separates read-access from write; gets `audit.read` specifically.

### When to start here

Your app has hierarchy (campus > building > room; region > market > branch; etc.) and multiple tiers of "manage my slice" personas.

---

## HR Coordinator — per-person workflow pattern

**Use when:** your app's unit of work is a person (employee, patient, student, participant), each has their own workflow instance, and access needs scope down to the individual.

```python
seed_roles = {
    "admin": ["*"],
    "hr_editor": [                         # tenant-wide, full workflow
        "employee.read", "employee.create", "employee.edit",
        "view.cross_department",
        "task.read", "task.update_status",
        "template.read", "template.edit",
        "notification.edit", "training.edit",
        "email.read", "email.approve", "email.send",
        "calendar.read", "calendar.schedule",
        "audit.read",
    ],
    "department_manager": [                # scoped to department
        "employee.read", "employee.edit",
        "task.read", "task.update_status",
        "email.read", "email.approve",
        "calendar.read", "calendar.schedule",
    ],
    "employee_liaison": [                  # scoped to ONE employee id
        "employee.read",
        "task.read", "task.update_status",
        "calendar.read",
    ],
    "auditor": [                           # tenant-wide, read-only
        "employee.read", "view.cross_department",
        "task.read", "template.read",
        "email.read", "calendar.read", "audit.read",
    ],
    "reader": ["employee.read", "task.read", "calendar.read"],
}

scope_types = [
    ScopeType(id="department", label="Department", list_endpoint="..."),
    ScopeType(id="employee", label="Employee", list_endpoint="..."),
]
```

### Why the roles

- Three-tier scoping: tenant (hr_editor), department (department_manager), individual (employee_liaison). Three is the right number for workflow apps — any more and users can't reason about who sees what.
- `employee_liaison` scoped to one person is the unusual bit. Works for HR (buddy / onboarding sponsor) and generalizes to any "helper assigned to a single case" pattern.
- `auditor` with tenant-wide read + audit.read is identical to Crew's auditor. Steal it.

### When to start here

Your app's atomic unit is a person, there's typically one workflow per person, and real customers have described exactly these three tiers.

---

## Redactit — pipeline-roles pattern

**Use when:** your app is a multi-stage pipeline (request → review → release) where different personas own different stages.

```python
seed_roles = {
    "admin": ["*"],
    "requester": [                         # intake side
        "matter.read", "matter.create",
        "document.read", "document.upload",
    ],
    "reviewer": [                          # middle stage — human PII review
        "matter.read", "matter.edit",
        "document.read", "document.redact",
        "redaction.approve",
    ],
    "releaser": [                          # terminal action — send
        "matter.read", "document.read",
        "redaction.read", "release.create",
    ],
    "auditor": [                           # read + audit
        "matter.read", "document.read",
        "redaction.read", "release.read", "audit.read",
    ],
    "reader": ["matter.read", "document.read"],
}

scope_types = [
    ScopeType(id="matter", label="Matter", list_endpoint="..."),
    ScopeType(id="document", label="Document", list_endpoint="..."),
]
```

### Why the roles

- Roles name **pipeline stages**, not capability tiers. A user at stage N needs permissions for their stage + read on earlier stages. That's unusual — most apps build around capability tiers (edit/read/admin).
- No "editor" role because the app has no free-form edit — only stage-specific actions.
- `redaction.approve` is a terminal action (lock the redaction set); separate from `document.redact` (make redaction marks) to separate the reviewer from the approver if needed.

### When to start here

Your app models a workflow where each record moves through explicit stages, and ownership of each stage is distinct (different people do intake vs. review vs. approval).

---

## Patterns shared across all five

Every one of the five shipped apps has:

1. **`admin` with `permissions=["*"]`, `editable=False`.** Never customize. Never remove. Auto-updates when new permissions land.
2. **One "full-power editor" role** with most capabilities but not `roles.manage` or `admin.view`. Name varies (`library_editor`, `scheduler`, `hr_editor`, `reviewer`/`releaser`).
3. **One `reader` role** at the bottom with minimal capabilities. Scope it to restrict blast radius.
4. **At least one `view.cross_<partition>` permission** — the enabler for the "sees all, edits one" pattern. Always pair with a scoped editor role.
5. **An `auditor` role** (three of five have it explicitly) with `audit.read` and tenant-wide read. Separate from admin because auditors shouldn't change anything.

Copy these five shapes into your Stage 1 manifest. You'll be wrong about the middle — that's fine (see [`ROLES.md`](ROLES.md)).

---

## Anti-patterns to avoid (seen in early commits, cleaned up later)

1. **`super_admin` above `admin`.** If `admin=["*"]` isn't enough, you're building something the pattern doesn't model. Fix the underlying design.
2. **Role per stage AND role per tier.** Pick one. Redactit has pipeline roles (no tier-based edit/read), HR has tier roles (no per-stage). Both work; mixing confuses.
3. **Permission per route.** `employees_list / employees_detail / employees_search` because you have three endpoints. Collapse to `employee.read`.
4. **Role scoped to two scope types at once.** A role assignment has one scope. If you need "HR in Operations AND IT", make two assignments.
5. **Forgetting `audit.read`.** Compliance-adjacent apps always grow one; wire it at Stage 1 so it's there when asked for.
