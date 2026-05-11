/**
 * Cold Case domain API client.
 *
 * Endpoints map 1:1 to `server-py/routers/{cases,conversations,reports,audit}.py`.
 * The §13663 invariants (must-sign-before-export, first-AI-draft frozen on
 * promote, etc.) are enforced server-side; the client just surfaces the
 * resulting error messages via the existing axios interceptor.
 */

import { API_BASE_URL, http } from "./client";

// ── Types ──────────────────────────────────────────────────────────────────

export type CaseClassification =
  | "homicide" | "robbery" | "assault" | "burglary"
  | "sexual_assault" | "missing_person" | "other";

export type CaseStatus = "open" | "active" | "closed" | "reopened";

export type RetentionPolicy = "match_official_report" | "7y" | "indefinite";

export interface Case {
  id: string;
  case_number: string;
  title: string;
  classification: CaseClassification;
  status: CaseStatus;
  retention_policy: RetentionPolicy;
  primary_investigator_id: string;
  co_investigator_ids: string[];
  description: string;
  created_by: string;
  created_at: string | null;
  closed_at: string | null;
  last_activity_at: string | null;
}

export interface Document {
  id: string;
  case_id: string;
  storage_uri: string;
  sha256: string;
  original_filename: string;
  mime_type: string;
  page_count: number;
  size_bytes: number;
  uploaded_by: string;
  uploaded_at: string | null;
}

export type MediaSourceType =
  | "bodycam" | "dashcam" | "interview_audio" | "interview_video"
  | "call_recording" | "other";

export interface MediaInput {
  id: string;
  case_id: string;
  storage_uri: string;
  sha256: string;
  source_type: MediaSourceType;
  duration_seconds: number;
  captured_at: string | null;
  description: string;
  registered_by: string;
  registered_at: string | null;
}

export interface Conversation {
  id: string;
  case_id: string;
  user_id: string;
  title: string;
  started_at: string | null;
  last_message_at: string | null;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  parent_message_id: string | null;
  user_id: string;
  timestamp: string | null;
  model: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
  in_context_document_ids: string[];
  in_context_media_ids: string[];
  is_first_ai_draft: boolean;
  first_draft_locked_for_report_id: string | null;
}

export interface AIProgram {
  name: string;
  version: string;
  provider: string;
}

export interface OfficerSignature {
  user_id: string;
  display_name: string;
  badge_number: string;
  signed_at: string | null;
  content_sha256: string;
  attestation_text: string;
}

export type ReportStatus = "draft" | "signed" | "exported" | "superseded";

export interface ReportRevision {
  seq: number;
  text: string;
  editor_id: string;
  editor_display: string;
  timestamp: string | null;
  content_sha256: string;
  byte_count: number;
  note: string;
  is_signed_revision: boolean;
}

export interface Report {
  id: string;
  case_id: string;
  conversation_id: string;
  title: string;
  final_text: string;
  first_ai_draft_message_id: string;
  first_ai_draft_text_snapshot: string;
  ai_programs_used: AIProgram[];
  statutory_disclosure: string;
  status: ReportStatus;
  signature: OfficerSignature | null;
  revisions: ReportRevision[];
  exported_artifact_uri: string;
  export_target: string;
  exported_at: string | null;
  supersedes_report_id: string | null;
  created_by: string;
  created_at: string | null;
  signed_at: string | null;
}

export interface AuditEvent {
  id: string;
  timestamp: string | null;
  event_type: string;
  user_id: string;
  user_display: string;
  ip_address: string;
  case_id: string | null;
  conversation_id: string | null;
  message_id: string | null;
  report_id: string | null;
  document_id: string | null;
  media_id: string | null;
  summary: string;
  detail: Record<string, unknown>;
}

// ── Cases ──────────────────────────────────────────────────────────────────

export async function listCases(): Promise<Case[]> {
  const { data } = await http.get<{ cases: Case[] }>("/cases");
  return data.cases;
}

export async function getCase(id: string): Promise<{
  case: Case; documents: Document[]; media: MediaInput[];
}> {
  const { data } = await http.get(`/cases/${id}`);
  return data;
}

export async function createCase(body: {
  case_number: string;
  title: string;
  classification: CaseClassification;
  retention_policy?: RetentionPolicy;
  description?: string;
}): Promise<Case> {
  const { data } = await http.post<Case>("/cases", body);
  return data;
}

export async function updateCase(id: string, body: Partial<{
  title: string;
  classification: CaseClassification;
  retention_policy: RetentionPolicy;
  description: string;
  status: CaseStatus;
}>): Promise<Case> {
  const { data } = await http.patch<Case>(`/cases/${id}`, body);
  return data;
}

export type ExtractionMethod = "text-layer" | "ocr" | "plaintext" | "empty" | "error";

export interface DocumentTextStatus {
  document_id: string;
  filename: string;
  method: ExtractionMethod;
  chars: number;
  non_ws_chars: number;
  line_count: number;
}

export async function getDocumentText(caseId: string, documentId: string): Promise<{
  document: Document;
  text: string;
  lines: string[];
  line_count: number;
  extraction_method: ExtractionMethod;
}> {
  const { data } = await http.get(`/cases/${caseId}/documents/${documentId}/text`);
  return data;
}

export async function getDocumentTextStatus(caseId: string, documentId: string): Promise<DocumentTextStatus> {
  const { data } = await http.get(`/cases/${caseId}/documents/${documentId}/text-status`, { timeout: 120000 });
  return data;
}

export async function registerDocument(caseId: string, body: {
  storage_uri: string;
  original_filename: string;
  mime_type?: string;
  sha256?: string;
  page_count?: number;
  size_bytes?: number;
}): Promise<Document> {
  const { data } = await http.post<Document>(`/cases/${caseId}/documents`, body);
  return data;
}

export async function uploadDocument(
  caseId: string,
  file: File,
  mimeTypeOverride?: string,
): Promise<Document> {
  // Server accepts up to 50 MB. We let the request fail naturally past that
  // rather than reimplementing the limit here — single source of truth.
  const form = new FormData();
  form.append("file", file);
  if (mimeTypeOverride) form.append("mime_type_override", mimeTypeOverride);
  const { data } = await http.post<Document>(
    `/cases/${caseId}/documents/upload`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function registerMedia(caseId: string, body: {
  storage_uri: string;
  source_type: MediaSourceType;
  sha256?: string;
  duration_seconds?: number;
  captured_at?: string;
  description?: string;
}): Promise<MediaInput> {
  const { data } = await http.post<MediaInput>(`/cases/${caseId}/media`, body);
  return data;
}

// ── Conversations ──────────────────────────────────────────────────────────

export async function listConversations(caseId: string): Promise<Conversation[]> {
  const { data } = await http.get<{ conversations: Conversation[] }>(`/cases/${caseId}/conversations`);
  return data.conversations;
}

export async function startConversation(caseId: string, title = ""): Promise<Conversation> {
  const { data } = await http.post<Conversation>(`/cases/${caseId}/conversations`, { title });
  return data;
}

export async function listMessages(conversationId: string): Promise<{
  conversation: Conversation; messages: Message[];
}> {
  const { data } = await http.get(`/conversations/${conversationId}/messages`);
  return data;
}

export async function sendMessage(conversationId: string, body: {
  content: string;
  parent_message_id?: string;
  in_context_document_ids?: string[];
  in_context_media_ids?: string[];
}): Promise<{ user_message: Message; assistant_message: Message }> {
  // 5 min — multimodal PDF chat against large cases can run 60–120s on gpt-5.5.
  // The user-visible Send button surfaces an elapsed-time counter so the
  // wait feels intentional rather than hung.
  const { data } = await http.post(`/conversations/${conversationId}/messages`, body, {
    timeout: 300_000,
  });
  return data;
}

// ── Reports ────────────────────────────────────────────────────────────────

export async function listReportsForCase(caseId: string): Promise<Report[]> {
  const { data } = await http.get<{ reports: Report[] }>(`/reports/cases/${caseId}/reports`);
  return data.reports;
}

export async function getReport(id: string): Promise<Report> {
  const { data } = await http.get<Report>(`/reports/${id}`);
  return data;
}

export async function promoteMessageToReport(body: {
  title: string;
  message_id: string;
  initial_final_text?: string;
}): Promise<Report> {
  const { data } = await http.post<Report>(`/reports/promote`, body);
  return data;
}

export async function editReport(id: string, body: {
  title?: string;
  final_text?: string;
  additional_ai_programs?: AIProgram[];
}): Promise<Report> {
  const { data } = await http.patch<Report>(`/reports/${id}`, body);
  return data;
}

export async function signReport(id: string, body: {
  // F19 — display_name is intentionally NOT accepted; the server derives it
  // from the authenticated UserContext. Only badge_number is body-controlled.
  badge_number?: string;
  attestation_text?: string;
}): Promise<Report> {
  const { data } = await http.post<Report>(`/reports/${id}/sign`, body);
  return data;
}

export async function exportReport(id: string, target: "file" | "evidence.com" = "file"): Promise<Report> {
  const { data } = await http.post<Report>(`/reports/${id}/export`, { target });
  return data;
}

export function reportPdfUrl(id: string): string {
  // Browser-loadable via the Vite /launchpad/* proxy → backend.
  return `${API_BASE_URL}/reports/${id}/pdf`;
}

// F7 — Chain-of-Custody PDF (auto-paired with signed report on export).
export function reportChainPdfUrl(id: string): string {
  return `${API_BASE_URL}/reports/${id}/chain.pdf`;
}

// F9 — Officer's Editorial Work diff (PDF view).
export function reportDiffPdfUrl(id: string): string {
  return `${API_BASE_URL}/reports/${id}/diff.pdf`;
}

export interface DiffSegment {
  op: "equal" | "officer_added" | "ai_wrote_removed";
  text: string;
}

export interface ReportDiff {
  report_id: string;
  first_ai_draft: string;
  compared_to: string;
  compared_to_label: string;
  segments: DiffSegment[];
  stats: {
    ai_first_chars: number;
    compared_to_chars: number;
    similarity_ratio: number;
    no_edits: boolean;
  };
}

export async function getReportDiff(id: string): Promise<ReportDiff> {
  const { data } = await http.get<ReportDiff>(`/reports/${id}/diff`);
  return data;
}

// F8 — Discovery Package
export interface DiscoveryPackage {
  case_id: string;
  case_number: string;
  zip_filename: string;
  zip_uri: string;
  zip_sha256: string;
  zip_size_bytes: number;
  manifest_sha256: string;
  file_count: number;
  report_count: number;
  document_count: number;
  media_count: number;
  include_source_binaries: boolean;
}

export async function exportDiscoveryPackage(caseId: string, body: {
  reason: string;
  report_ids?: string[];
  include_source_binaries?: boolean;
}): Promise<DiscoveryPackage> {
  const { data } = await http.post<DiscoveryPackage>(
    `/cases/${caseId}/discovery-package`,
    body,
    { timeout: 180_000 },
  );
  return data;
}

export function discoveryPackageDownloadUrl(caseId: string, zipFilename: string): string {
  return `${API_BASE_URL}/cases/${caseId}/discovery-package/${encodeURIComponent(zipFilename)}`;
}

// ── Audit ──────────────────────────────────────────────────────────────────

export async function getReportChain(reportId: string): Promise<{
  report: Report;
  conversation: Conversation;
  case: Case;
  chain: (Message & { statutory_note?: string })[];
  audit_events: AuditEvent[];
  statutory_attestation: {
    penal_code: string;
    disclosure: string;
    ai_programs_used: AIProgram[];
  };
}> {
  const { data } = await http.get(`/audit/reports/${reportId}/chain`);
  return data;
}

export async function listAuditEvents(filter: {
  case_id?: string;
  user_id?: string;
  event_type?: string;
  since?: string;
  until?: string;
  limit?: number;
} = {}): Promise<{ events: AuditEvent[]; count: number }> {
  const params = new URLSearchParams();
  Object.entries(filter).forEach(([k, v]) => { if (v != null) params.set(k, String(v)); });
  const { data } = await http.get(`/audit/events?${params.toString()}`);
  return data;
}

// ── Prompts ────────────────────────────────────────────────────────────────

export interface PromptSuggestion {
  id: string;
  label: string;
  category: string;
  description: string;
  needs_document: boolean;
  rendered_prompt: string;
}

export async function listPromptSuggestions(params: {
  case_id?: string;
  document_id?: string;
}): Promise<{
  suggestions: PromptSuggestion[];
  context: {
    case_id: string | null;
    document_id: string | null;
    active_document_label: string | null;
    all_documents_label: string | null;
  };
}> {
  const search = new URLSearchParams();
  if (params.case_id) search.set("case_id", params.case_id);
  if (params.document_id) search.set("document_id", params.document_id);
  const { data } = await http.get(`/prompts/suggestions?${search.toString()}`);
  return data;
}

// ── Demo ───────────────────────────────────────────────────────────────────

export async function seedSyntheticDemo(): Promise<{
  created: boolean;
  case_id: string;
  documents: string[];
  media: string[];
}> {
  const { data } = await http.post(`/demo/seed-synthetic`);
  return data;
}

export async function seedCivilRightsCases(): Promise<{
  cases: { case_id: string; case_number: string; created: boolean; documents?: string[]; regenerated_pdfs?: number }[];
  errors: { case_number: string; error: string }[];
}> {
  const { data } = await http.post(`/demo/seed-civil-rights`, undefined, { timeout: 180000 });
  return data;
}

export async function getCaseAuditSummary(caseId: string): Promise<{
  case: Case;
  event_counts: Record<string, number>;
  total_events: number;
  reports: { id: string; title: string; status: ReportStatus; signed_at: string | null }[];
  distinct_ai_programs: { name: string; version: string }[];
}> {
  const { data } = await http.get(`/audit/cases/${caseId}/summary`);
  return data;
}
