"""
Cold Case — Launchpad Admin permission catalog + seed roles.

Permission vocabulary follows resource.action naming. Statutory requirements
from California Penal Code §13663 (SB-524) shape several permissions —
see docs/comprehensive-prd.md §12 for the mapping.
"""

from launchpad_admin.manifest import AppManifest, PermissionMeta, SeedRole


APP_MANIFEST = AppManifest(
    app_id="coldcase",
    display_name="Cold Case",

    permissions={
        # ── Cases ─────────────────────────────────────────────────────────
        "case.read":   PermissionMeta(label="View cases", group="Cases"),
        "case.create": PermissionMeta(label="Create cases", group="Cases"),
        "case.edit":   PermissionMeta(label="Edit cases", group="Cases"),
        "case.close":  PermissionMeta(label="Close / reopen cases", group="Cases"),

        # ── Documents & media ─────────────────────────────────────────────
        "document.register": PermissionMeta(
            label="Register documents to a case",
            description="Add a pointer (URI + hash) to a document stored in agency storage. Cold Case never holds the binary.",
            group="Documents",
        ),
        "media.register": PermissionMeta(
            label="Register media (bodycam / audio / video) inputs",
            description="Required by Penal Code §13663(c)(2) — track media used as AI input.",
            group="Documents",
        ),

        # ── AI interactions ───────────────────────────────────────────────
        "conversation.create": PermissionMeta(
            label="Start AI conversations on a case",
            group="AI",
        ),
        "conversation.read": PermissionMeta(
            label="Read AI conversations on a case",
            group="AI",
        ),

        # ── Official reports (§13663 path) ────────────────────────────────
        "report.draft": PermissionMeta(
            label="Promote an AI output to a report draft",
            description="Selects an AI message as the §13663 'first draft' and freezes it.",
            group="Reports",
        ),
        "report.sign": PermissionMeta(
            label="Sign and export an official report",
            description="§13663(a)(2) requires the officer's signature attesting they reviewed contents and facts are true. Only the drafting officer should hold this.",
            group="Reports",
        ),
        "report.export": PermissionMeta(
            label="Push signed reports to evidence.com / external system",
            group="Reports",
        ),

        # ── Audit / compliance (§13663(c)) ────────────────────────────────
        "audit.read": PermissionMeta(
            label="View audit trail and SB-524 compliance reports",
            description="City attorney / city auditor access to the full prompt chain for any approved artifact.",
            group="Audit",
        ),
        "audit.export": PermissionMeta(
            label="Export audit packages (PDF / JSON)",
            group="Audit",
        ),
        "retention.manage": PermissionMeta(
            label="Set per-case retention policies",
            description="Defaults to 'match_official_report' per §13663(b). Homicide → indefinite.",
            group="Audit",
        ),

        # ── Vendor access (§13663(d), F10/F20) ────────────────────────────
        "vendor_access.request": PermissionMeta(
            label="Open a vendor access request",
            description="Darwin operator opens a §13663(d) carve-out access request. Customer roles (detective, sergeant, auditor) do NOT hold this.",
            group="Vendor access",
        ),
        "vendor_access.approve": PermissionMeta(
            label="Approve / deny / revoke a vendor access request",
            description="Agency admin only — separation of duties from `vendor_access.request`. Typically held by the city attorney or records officer.",
            group="Vendor access",
        ),

        # ── Administration (required) ─────────────────────────────────────
        "admin.view": PermissionMeta(
            label="Access admin panel",
            group="Administration",
        ),
        "roles.manage": PermissionMeta(
            label="Manage roles and assignments",
            description="Create custom roles, edit roles, assign/revoke users",
            group="Administration",
        ),
    },

    seed_roles={
        # Full admin — typically the agency's IT / records admin.
        "admin": SeedRole(
            permissions=["*"],
            description="Full administrative access (IT / records admin).",
            editable=False,
        ),

        # Detective — drafts and signs their own reports. Cannot read others' audit.
        "detective": SeedRole(
            permissions=[
                "case.read", "case.create", "case.edit",
                "document.register", "media.register",
                "conversation.create", "conversation.read",
                "report.draft", "report.sign", "report.export",
            ],
            description="Cold case investigator. Drafts, signs, and exports their own §13663 reports.",
            editable=True,
        ),

        # Supervising sergeant — full case visibility + can close + can read audit.
        "sergeant": SeedRole(
            permissions=[
                "case.read", "case.edit", "case.close",
                "document.register", "media.register",
                "conversation.create", "conversation.read",
                "report.draft", "report.sign", "report.export",
                "audit.read",
                "retention.manage",
            ],
            description="Supervising sergeant. Reviews investigators' work and manages retention.",
            editable=True,
        ),

        # Auditor — city attorney / auditor. Read-only over audit trail.
        "auditor": SeedRole(
            permissions=[
                "case.read",
                "conversation.read",
                "audit.read", "audit.export",
            ],
            description="City attorney or auditor. Read-only access to the §13663 audit trail.",
            editable=True,
        ),

        # Read-only — patrol or analyst with case-list visibility only.
        "viewer": SeedRole(
            permissions=["case.read"],
            description="Read-only access to case metadata.",
            editable=True,
        ),
    },

    # Cases are the natural scope. Role assignments can be tenant-wide
    # (e.g. records admin sees everything) or case-scoped (e.g. an outside
    # consultant gets access to one case only). Phase 2 — leave None for MVP.
    scope_type=None,
    scope_list_endpoint=None,
)
