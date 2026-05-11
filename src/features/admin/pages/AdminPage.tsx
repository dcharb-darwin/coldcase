import { AdminShell } from "@/launchpad-admin";

/** Admin console — roles, assignments, AD mappings, AI assistant. */
export default function AdminPage() {
  return <AdminShell apiBase="/launchpad/coldcase/api/admin" />;
}
