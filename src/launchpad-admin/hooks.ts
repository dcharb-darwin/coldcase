/**
 * Permission hooks. All read from the UserContextProvider's cached /admin/me
 * response — no network traffic per check.
 */
import { useUserContext } from "./UserContextProvider";

/** Returns true if the current user holds `permission` — tenant-wide, or
 * (when scopeType + scopeId are given) within that specific scope instance.
 * SA always returns true.
 *
 * Back-compat: callers passing only scopeId still work — the lookup matches
 * across every scope_type for that id.
 */
export function usePermission(
  permission: string,
  scopeType?: string | null,
  scopeId?: string | null,
): boolean {
  const { me } = useUserContext();
  if (!me) return false;
  if (me.is_super_admin) return true;
  if (me.permissions.includes(permission)) return true;
  if (scopeId) {
    if (scopeType) {
      const scoped = me.scoped_permissions[`${scopeType}:${scopeId}`];
      if (scoped?.includes(permission)) return true;
    } else {
      for (const [key, perms] of Object.entries(me.scoped_permissions)) {
        if (key.endsWith(`:${scopeId}`) && perms.includes(permission)) return true;
      }
    }
  }
  return false;
}

/** Convenience — returns true if the user holds *any* of the listed permissions. */
export function useAnyPermission(
  permissions: string[],
  scopeType?: string | null,
  scopeId?: string | null,
): boolean {
  const { me } = useUserContext();
  if (!me) return false;
  if (me.is_super_admin) return true;
  for (const p of permissions) {
    if (me.permissions.includes(p)) return true;
    if (scopeId) {
      if (scopeType) {
        if (me.scoped_permissions[`${scopeType}:${scopeId}`]?.includes(p)) return true;
      } else {
        for (const [key, perms] of Object.entries(me.scoped_permissions)) {
          if (key.endsWith(`:${scopeId}`) && perms.includes(p)) return true;
        }
      }
    }
  }
  return false;
}

/** True if the user holds the named role in the current app+tenant. Prefer
 * usePermission for most gates — roles are vocabulary, permissions are behavior. */
export function useHasRole(roleName: string): boolean {
  const { me } = useUserContext();
  return !!me && (me.is_super_admin || me.roles.includes(roleName));
}
