import { isAdminRoute, isAuditRoute, isCaseDetailRoute, isCaseListRoute, ROUTES } from "./routes";

export type BreadcrumbItem = {
  label: string;
  /** `null` = current page (not a link) */
  path: string | null;
};

export type BreadcrumbTrailOptions = {
  detailLabel?: string | null;
};

export function breadcrumbTrail(path: string, _options?: BreadcrumbTrailOptions): BreadcrumbItem[] {
  if (isAdminRoute(path)) {
    return [
      { label: "Cases", path: ROUTES.cases },
      { label: "Administration", path: null },
    ];
  }
  if (isCaseDetailRoute(path)) {
    return [
      { label: "Cases", path: ROUTES.cases },
      { label: _options?.detailLabel || "Case", path: null },
    ];
  }
  if (isCaseListRoute(path)) {
    return [{ label: "Cases", path: null }];
  }
  if (isAuditRoute(path)) {
    return [
      { label: "Cases", path: ROUTES.cases },
      { label: "Audit", path: null },
    ];
  }
  return [{ label: "Cases", path: null }];
}
