/**
 * Axios HTTP client for Cold Case.
 *
 * Two interceptors per Launchpad pattern (see docs/PATTERNS.md §2):
 * - Request: attach X-Impersonate-User-Id when SA is impersonating.
 * - Response: rewrite FastAPI `detail` into Error.message so UI gets clean text.
 */

import axios, { AxiosError, type AxiosInstance } from "axios";
import { impersonation } from "../../launchpad-admin";

export const API_BASE_URL = "/launchpad/coldcase/api";

// 60s timeout to accommodate LLM calls (person/tag/timeline/inferred-mention
// suggesters, next-step suggester, chat sends). 10s was too tight for the
// inferred-mention extraction on multi-doc cases — OpenAI routinely takes
// 8-15s for that prompt size.
const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

http.interceptors.request.use((config) => {
  const id = impersonation.get();
  if (id) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>)["X-Impersonate-User-Id"] = id;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string | Array<{ msg?: string }> }>) => {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      error.message = detail;
    } else if (Array.isArray(detail)) {
      const first = detail.find((d) => d && typeof d.msg === "string");
      if (first?.msg) error.message = first.msg;
    }
    return Promise.reject(error);
  }
);

export { http };

// Add domain client functions below as features land. Example:
//
// export async function listEmployees(): Promise<Employee[]> {
//   const response = await http.get<Employee[]>("/employees");
//   return response.data;
// }
