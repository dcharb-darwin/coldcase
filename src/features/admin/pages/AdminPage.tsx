import { AdminShell } from "@/launchpad-admin";
import CompliancePreflightCard from "../components/CompliancePreflightCard";

/** Admin console — preflight checklist on top, then Launchpad Admin (roles,
 *  assignments, AD mappings, AI assistant). */
export default function AdminPage() {
  return (
    <div className="space-y-4 p-4">
      <CompliancePreflightCard />
      <AdminShell apiBase="/launchpad/coldcase/api/admin" />
    </div>
  );
}
