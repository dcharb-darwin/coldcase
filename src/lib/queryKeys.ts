/**
 * Centralized React Query keys.
 * Add per-feature keys here as features land. Keep keys typed as `as const`
 * tuples so React Query's cache addressing stays type-safe.
 */

export const queryKeys = {
  // Example:
  // employees: ["employees"] as const,
  // employeeDetail: (id: string) => ["employeeDetail", id] as const,
} as const;
