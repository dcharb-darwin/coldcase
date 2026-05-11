/** Types shared between the admin UI and the backend router. */

export interface PermissionMeta {
  label: string;
  description?: string;
  group: string;
}

export interface SeedRoleDef {
  permissions: string[];
  description: string;
  editable: boolean;
}

export interface ScopeTypeDef {
  id: string;
  label: string;
  description?: string;
  list_endpoint: string | null;
}

/** Returned by GET /admin/manifest — drives the role editor UI. */
export interface ManifestResponse {
  app_id: string;
  display_name: string;
  /** Legacy single-scope field — prefer `scope_types`. */
  scope_type: string | null;
  scope_list_endpoint: string | null;
  /** Canonical list of scope types this app supports. */
  scope_types: ScopeTypeDef[];
  permissions: Record<string, PermissionMeta>;
  seed_roles: Record<string, SeedRoleDef>;
}

/** Returned by GET /admin/me — the current user's effective access. */
export interface MeResponse {
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  tenant_id: string;
  tenant_name: string;
  is_super_admin: boolean;
  permissions: string[];
  /** Keys are composite "<scope_type>:<scope_id>" strings. */
  scoped_permissions: Record<string, string[]>;
  /** Names of roles the user effectively holds. Mapping-derived rows include
   * an `(via AD: <group>)` or `(via dept: <value>)` suffix for clarity. */
  roles: string[];
  /** Identity claims from Govern — used to show why mappings applied. */
  govern_roles?: string[];
  attributes?: Record<string, unknown>;
  /** Populated when the current request is SA-impersonating this user. */
  impersonator_user_id?: string | null;
  impersonator_email?: string;
}

export interface Role {
  id: string;
  tenant_id: string;
  app_id: string;
  name: string;
  description: string;
  permissions: string[];
  is_system: boolean;
  is_system_editable: boolean;
  created_at: string | null;
  updated_at: string | null;
}

/** One action proposed by the AI assistant. Applied via the matching
 * /admin/{roles|assignments|mappings} endpoint after the admin reviews it.
 *
 * The `review_*` and `original_*` fields come from the second-stage reviewer
 * agent that critiques the proposer before the admin sees the result. */
export interface ProposedAction {
  kind: "create_role" | "assign_role" | "create_mapping" | string;
  body: Record<string, unknown>;
  summary: string;
  warnings: string[];
  valid: boolean;
  review_verdict: "approved" | "modified" | "rejected" | "added" | string;
  review_notes: string;
  /** Proposer's original body, populated when the reviewer modified/rejected. */
  original_body: Record<string, unknown> | null;
  original_summary: string;
}

export interface AssistResponse {
  understanding: string;
  actions: ProposedAction[];
  /** Clarifying questions — either agent (proposer or reviewer) may emit
   * these when the request is too ambiguous to propose concrete actions.
   * The UI should encourage the admin to answer and re-prompt. */
  questions: string[];
  notes: string;
  model: string;
  reviewer_model?: string | null;
  reviewer_ran?: boolean;
  reviewer_summary?: string;
  error?: string;
}

export interface RoleMapping {
  id: string;
  tenant_id: string;
  app_id: string;
  match_type: "ad_group" | "department";
  match_value: string;
  role_id: string;
  role_name: string;
  scope_type: string | null;
  scope_id: string | null;
  notes: string;
  created_at: string | null;
  created_by: string;
}

export interface RoleAssignment {
  id: string;
  user_id: string;
  tenant_id: string;
  app_id: string;
  role_id: string;
  role_name: string;
  scope_type: string | null;
  scope_id: string | null;
  granted_by: string;
  granted_at: string | null;
}
