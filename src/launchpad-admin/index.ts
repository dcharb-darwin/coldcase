/** Public surface of the admin package. Apps import from this entry point. */
export { AdminShell } from "./AdminShell";
export { Can } from "./Can";
export { UserContextProvider, useUserContext } from "./UserContextProvider";
export { usePermission, useAnyPermission, useHasRole } from "./hooks";
export { adminApi, configureAdminApi, configureAdminHeaders } from "./api";
export { impersonation, impersonationHeader } from "./impersonation";
export type {
  PermissionMeta,
  SeedRoleDef,
  ScopeTypeDef,
  ManifestResponse,
  MeResponse,
  Role,
  RoleAssignment,
  RoleMapping,
  ProposedAction,
  AssistResponse,
} from "./types";
