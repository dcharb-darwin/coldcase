/**
 * <Can> — conditionally render children based on a permission check.
 *
 * Remember: this is UI affordance, not security. The backend decorator is the
 * real gate. <Can> just hides buttons that would 403.
 *
 * Usage:
 *   <Can permission="sop.delete">
 *     <button onClick={handleDelete}>Delete SOP</button>
 *   </Can>
 *
 *   <Can permission="sop.edit_any" fallback={<span>Read-only</span>}>
 *     <button>Edit</button>
 *   </Can>
 *
 *   <Can anyOf={["sop.accept", "sop.edit_any"]}>
 *     <button>Review</button>
 *   </Can>
 */
import type { ReactNode } from "react";
import { useAnyPermission, usePermission } from "./hooks";

interface CanProps {
  /** Single permission required. Mutually exclusive with `anyOf`. */
  permission?: string;
  /** Show when the user has at least one of these. */
  anyOf?: string[];
  /** Scope type id — e.g. "owner_group" or "sop". Required when scopeId is set
   * for strict per-type checks; omit to match across any scope type. */
  scopeType?: string | null;
  /** Scope resource id, e.g. an owner_group_id or a sop_id. */
  scopeId?: string | null;
  /** Rendered when the check fails. Defaults to null (nothing). */
  fallback?: ReactNode;
  children: ReactNode;
}

export function Can({ permission, anyOf, scopeType, scopeId, fallback = null, children }: CanProps) {
  const singleOk = permission ? usePermission(permission, scopeType, scopeId) : false;
  const anyOk = anyOf ? useAnyPermission(anyOf, scopeType, scopeId) : false;
  const ok = permission ? singleOk : anyOf ? anyOk : false;
  return <>{ok ? children : fallback}</>;
}
