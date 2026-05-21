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
  external_id: string;
  agency_ori_snapshot: string;
  title: string;
  classification: CaseClassification;
  status: CaseStatus;
  retention_policy: RetentionPolicy;
  primary_investigator_id: string;
  co_investigator_ids: string[];
  description: string;
  date_of_incident: string | null;
  created_by: string;
  created_at: string | null;
  closed_at: string | null;
  last_activity_at: string | null;
  /** User-applied tag list (case-scope assignments). Embedded by list/detail. */
  tags?: Tag[];
  /** Server-computed system tags (signed-report, vendor-accessed, etc.). */
  system_tags?: Tag[];
}

export interface Document {
  id: string;
  case_id: string;
  external_id: string;
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
  external_id: string;
  evidence_com_asset_id: string;
  evidence_com_pushed_at: string | null;
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

export async function listCases(opts: { mine?: boolean; limit?: number } = {}): Promise<Case[]> {
  const params: Record<string, string> = {};
  if (opts.mine) params.mine = "true";
  if (opts.limit) params.limit = String(opts.limit);
  const { data } = await http.get<{ cases: Case[] }>("/cases", { params });
  return data.cases;
}

export interface CompliancePreflightCheck {
  id: string;
  label: string;
  statute_ref: string;
  passed: boolean;
  detail: string;
}

export interface CompliancePreflight {
  ready: boolean;
  environment: string;
  service: string;
  checks: CompliancePreflightCheck[];
  failed_check_ids: string[];
}

export async function getCompliancePreflight(): Promise<CompliancePreflight> {
  const { data } = await http.get<CompliancePreflight>("/admin/compliance/preflight");
  return data;
}

export interface AuditChainBreak {
  sequence: number;
  index: number;
  kind: "sequence_gap" | "prev_hash_mismatch" | "event_hash_mismatch";
  detail: string;
  event_id: string;
}

export interface AuditChainReport {
  tenant_id: string;
  ok: boolean;
  event_count: number;
  pre_chain_event_count: number;
  tip_hash: string;
  breaks: AuditChainBreak[];
}

export async function getAuditChainReport(): Promise<AuditChainReport> {
  const { data } = await http.get<AuditChainReport>("/admin/compliance/audit-chain");
  return data;
}

// ── Tags ─────────────────────────────────────────────────────────────────

export type TagKind = "system" | "user";
export type TagSubjectKind = "case" | "document" | "message" | "report";
export type TagColor =
  | "slate" | "red" | "amber" | "emerald"
  | "blue" | "indigo" | "purple" | "pink";

export interface Tag {
  id: string;
  label: string;
  slug: string;
  description: string;
  kind: TagKind;
  color: TagColor;
  applicable_to: TagSubjectKind[];
  created_by: string;
  created_at: string | null;
}

export interface TagAssignment {
  id: string;
  tag_id: string;
  subject_kind: TagSubjectKind;
  subject_id: string;
  case_id: string | null;
  applied_by: string;
  applied_at: string | null;
  provenance?: Provenance | null;
}

export interface CaseTagAssignment extends TagAssignment {
  tag: Tag;
}

export async function listTags(): Promise<Tag[]> {
  const { data } = await http.get<{ tags: Tag[] }>("/tags");
  return data.tags;
}

export async function listCaseTags(caseId: string): Promise<CaseTagAssignment[]> {
  const { data } = await http.get<{ assignments: CaseTagAssignment[] }>(
    `/cases/${caseId}/tags`,
  );
  return data.assignments;
}

export type ProvenanceSource = "manual" | "ai_suggested";

export interface Provenance {
  source: ProvenanceSource;
  suggested_by_model: string;
  suggested_rationale: string;
  accepted_at: string | null;
  accepted_by: string;
}

export interface AssignTagOptions {
  source?: ProvenanceSource;
  suggested_by_model?: string;
  suggested_rationale?: string;
}

export async function assignTag(
  tagId: string,
  subjectKind: TagSubjectKind,
  subjectId: string,
  options?: AssignTagOptions,
): Promise<TagAssignment> {
  const { data } = await http.post<TagAssignment>(
    `/tags/${tagId}/assign/${subjectKind}/${subjectId}`,
    options,
  );
  return data;
}

export async function unassignTag(
  tagId: string,
  subjectKind: TagSubjectKind,
  subjectId: string,
): Promise<void> {
  await http.delete(`/tags/${tagId}/assign/${subjectKind}/${subjectId}`);
}

export interface TagSuggestion {
  tag: Tag;
  rationale: string;
}

export async function suggestCaseTags(caseId: string): Promise<{
  suggestions: TagSuggestion[];
  model?: string;
  reason?: string;
}> {
  const { data } = await http.post(`/cases/${caseId}/tags/suggestions`);
  return data;
}

// ── Persons ──────────────────────────────────────────────────────────────

export type PersonRole =
  | "suspect" | "witness" | "victim" | "officer"
  | "person_of_interest" | "other";

export interface Person {
  id: string;
  case_id: string;
  name: string;
  role: PersonRole;
  descriptor: string;
  notes: string;
  created_by: string;
  created_at: string | null;
  provenance?: Provenance | null;
}

export async function listPersons(caseId: string): Promise<Person[]> {
  const { data } = await http.get<{ persons: Person[] }>(`/cases/${caseId}/persons`);
  return data.persons;
}

export async function createPerson(caseId: string, body: {
  name: string;
  role?: PersonRole;
  descriptor?: string;
  notes?: string;
  source?: ProvenanceSource;
  suggested_by_model?: string;
  suggested_rationale?: string;
}): Promise<Person> {
  const { data } = await http.post<Person>(`/cases/${caseId}/persons`, body);
  return data;
}

export async function deletePerson(caseId: string, personId: string): Promise<void> {
  await http.delete(`/cases/${caseId}/persons/${personId}`);
}

export interface PersonSuggestion {
  name: string;
  role: PersonRole;
  descriptor: string;
  rationale: string;
}

export async function suggestCasePersons(caseId: string): Promise<{
  suggestions: PersonSuggestion[];
  model?: string;
  reason?: string;
}> {
  const { data } = await http.post(`/cases/${caseId}/persons/suggestions`);
  return data;
}

export interface PersonMatch {
  case_id: string;
  case_number: string;
  case_title: string;
  case_classification: string;
  person_id: string;
  name: string;
  role: PersonRole;
  descriptor: string;
}

export async function searchPersons(
  name: string,
  opts?: { excludeCaseId?: string },
): Promise<{ matches: PersonMatch[]; normalized: string }> {
  const params: Record<string, string> = { name };
  if (opts?.excludeCaseId) params.exclude_case_id = opts.excludeCaseId;
  const { data } = await http.get<{ matches: PersonMatch[]; normalized: string }>(
    "/persons/search", { params },
  );
  return data;
}

// ── Case connections graph (derived) ─────────────────────────────────────

export interface ConnectionNode {
  id: string;
  kind: "case" | "person";
  // case fields
  case_id?: string;
  case_number?: string;
  case_title?: string;
  case_classification?: string;
  focal?: boolean;
  // person fields
  person_id?: string;
  name?: string;
  role?: PersonRole;
  descriptor?: string;
  ai_sourced?: boolean;
}

export interface ConnectionEdge {
  from: string;
  to: string;
  kind: "on_case" | "appears_on_other_case";
  other_role?: PersonRole;
}

export interface CaseConnections {
  case_id: string;
  nodes: ConnectionNode[];
  edges: ConnectionEdge[];
  stats: {
    persons_on_case: number;
    connected_cases: number;
    cross_case_edges: number;
  };
}

export async function getCaseConnections(caseId: string): Promise<CaseConnections> {
  const { data } = await http.get<CaseConnections>(`/cases/${caseId}/connections`);
  return data;
}

export interface SimilarCase {
  case_id: string;
  case_number: string;
  case_title: string;
  case_classification: CaseClassification;
  status: CaseStatus;
  score: number;
  shared_tag_slugs: string[];
  shared_tag_labels: string[];
}

export async function getSimilarCases(caseId: string): Promise<{
  focal_case_id: string;
  focal_tags?: string[];
  similar: SimilarCase[];
  reason?: string;
}> {
  const { data } = await http.get(`/cases/${caseId}/similar`);
  return data;
}

export interface RecurringPerson {
  name: string;
  role: PersonRole;
  case_count: number;
  your_case_ids: string[];
  your_case_numbers: string[];
  ai_sourced_any: boolean;
}

export interface SimilarCasePair {
  your_case_id: string;
  your_case_number: string;
  your_case_title: string;
  other_case_id: string;
  other_case_number: string;
  other_case_title: string;
  other_case_classification: string;
  other_is_yours: boolean;
  score: number;
  shared_tag_slugs: string[];
  shared_tag_labels: string[];
}

export interface DashboardInsights {
  recurring_persons: RecurringPerson[];
  similar_case_pairs: SimilarCasePair[];
}

export async function getDashboardInsights(): Promise<DashboardInsights> {
  const { data } = await http.get("/dashboard/insights");
  return data;
}

export interface InferredMention {
  descriptor: string;
  role_hint: PersonRole;
  rationale: string;
  source_doc_id: string;
  source_doc_filename: string;
  source_excerpt: string;
}

export async function suggestInferredMentions(caseId: string): Promise<{
  suggestions: InferredMention[];
  model?: string;
  reason?: string;
}> {
  const { data } = await http.post(`/cases/${caseId}/persons/inferred-mentions`);
  return data;
}

export async function acceptInferredMention(
  caseId: string,
  mention: InferredMention & { model: string },
): Promise<Note> {
  const { data } = await http.post(
    `/cases/${caseId}/persons/inferred-mentions/accept`,
    mention,
  );
  return data;
}

export interface DuplicatePersonPair {
  primary: Person;
  duplicate: Person;
}

export async function getDuplicatePersons(caseId: string): Promise<{
  pairs: DuplicatePersonPair[];
}> {
  const { data } = await http.get(`/cases/${caseId}/persons/duplicates`);
  return data;
}

export async function mergePersons(
  caseId: string,
  body: { primary_id: string; duplicate_id: string },
): Promise<Person> {
  const { data } = await http.post(`/cases/${caseId}/persons/merge`, body);
  return data;
}

// ── Hypotheses + brain dumps ────────────────────────────────────────────────

export type HypothesisStatus = "investigating" | "confirmed" | "disproved" | "superseded";
export type HypothesisFindingKind = "supporting" | "contradicting" | "gap";

export interface BrainDump {
  id: string;
  case_id: string;
  source: "typed" | "audio_recorded" | "audio_uploaded";
  audio_artifact_uri: string;
  audio_filename: string;
  audio_mime_type: string;
  audio_duration_seconds: string;
  transcript: string;
  transcript_model: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface HypothesisFinding {
  kind: HypothesisFindingKind;
  excerpt: string;
  rationale: string;
  source_doc_id: string;
  source_doc_filename: string;
  accepted_by: string;
  accepted_at: string | null;
  suggested_by_model: string;
}

export interface Hypothesis {
  id: string;
  case_id: string;
  title: string;
  body: string;
  rationale: string;
  status: HypothesisStatus;
  brain_dump_id: string | null;
  proposed_by_model: string;
  proposed_at: string | null;
  accepted_by: string;
  accepted_at: string | null;
  findings: HypothesisFinding[];
  created_by: string;
  created_at: string;
  updated_by: string;
  updated_at: string;
  status_changed_at: string | null;
}

export interface HypothesisSuggestion {
  title: string;
  body: string;
  rationale: string;
}

export async function createBrainDump(
  caseId: string,
  body: { transcript: string },
): Promise<BrainDump> {
  const { data } = await http.post(`/cases/${caseId}/brain-dumps`, body);
  return data;
}

export async function uploadAudioBrainDump(
  caseId: string,
  file: Blob,
  filename: string,
  source: "audio_recorded" | "audio_uploaded",
): Promise<BrainDump & { transcription_error?: string }> {
  const form = new FormData();
  form.append("file", file, filename);
  const { data } = await http.post(
    `/cases/${caseId}/brain-dumps/audio?source=${source}`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return data;
}

export async function updateBrainDump(
  caseId: string,
  dumpId: string,
  body: { transcript: string },
): Promise<BrainDump> {
  const { data } = await http.patch(`/cases/${caseId}/brain-dumps/${dumpId}`, body);
  return data;
}

export async function suggestHypotheses(
  caseId: string,
  brainDumpId: string,
): Promise<{ brain_dump_id: string; suggestions: HypothesisSuggestion[]; model?: string; reason?: string }> {
  const { data } = await http.post(
    `/cases/${caseId}/brain-dumps/${brainDumpId}/suggest-hypotheses`,
  );
  return data;
}

export async function createHypothesis(
  caseId: string,
  body: {
    title: string;
    body?: string;
    rationale?: string;
    brain_dump_id?: string;
    model?: string;
  },
): Promise<Hypothesis> {
  const { data } = await http.post(`/cases/${caseId}/hypotheses`, body);
  return data;
}

export async function listHypotheses(caseId: string): Promise<{ hypotheses: Hypothesis[] }> {
  const { data } = await http.get(`/cases/${caseId}/hypotheses`);
  return data;
}

export async function updateHypothesis(
  caseId: string,
  id: string,
  body: { title?: string; body?: string; status?: HypothesisStatus },
): Promise<Hypothesis> {
  const { data } = await http.patch(`/cases/${caseId}/hypotheses/${id}`, body);
  return data;
}

export async function deleteHypothesis(caseId: string, id: string): Promise<void> {
  await http.delete(`/cases/${caseId}/hypotheses/${id}`);
}

export async function checkHypothesis(
  caseId: string,
  id: string,
): Promise<{ findings: Omit<HypothesisFinding, "accepted_by" | "accepted_at" | "suggested_by_model">[]; model?: string; reason?: string }> {
  const { data } = await http.post(`/cases/${caseId}/hypotheses/${id}/check`);
  return data;
}

export async function acceptHypothesisFinding(
  caseId: string,
  id: string,
  body: {
    kind: HypothesisFindingKind;
    excerpt?: string;
    rationale?: string;
    source_doc_id?: string;
    source_doc_filename?: string;
    model?: string;
  },
): Promise<Hypothesis> {
  const { data } = await http.post(`/cases/${caseId}/hypotheses/${id}/findings`, body);
  return data;
}

export interface RelatedPerson {
  name: string;
  role: PersonRole;
  descriptor: string;
  on_case_id: string;
  on_case_number: string;
}

export interface PersonNetwork {
  query: string;
  normalized: string;
  matches: PersonMatch[];
  related_persons: RelatedPerson[];
}

export async function getPersonNetwork(
  name: string,
  opts?: { excludeCaseId?: string },
): Promise<PersonNetwork> {
  const params: Record<string, string> = { name };
  if (opts?.excludeCaseId) params.exclude_case_id = opts.excludeCaseId;
  const { data } = await http.get<PersonNetwork>("/persons/network", { params });
  return data;
}

export interface PersonMention {
  document_id: string;
  filename: string;
  line: number;
  snippet: string;
  matched_variant: string;
}

export async function getPersonMentions(
  caseId: string, personId: string,
): Promise<{ person_id: string; name: string; variants: string[]; mentions: PersonMention[] }> {
  const { data } = await http.get(`/cases/${caseId}/persons/${personId}/mentions`);
  return data;
}

// ── Timeline entries (detective-curated dated case events) ───────────────

export type TimelineEntrySource = "manual" | "ai_suggested";

export interface TimelineEntry {
  id: string;
  case_id: string;
  occurred_at: string;
  label: string;
  notes: string;
  source_document_id: string;
  source: TimelineEntrySource;
  rationale: string;
  created_by: string;
  created_at: string | null;
}

export interface TimelineEntrySuggestion {
  occurred_at: string;
  label: string;
  notes: string;
  source_document: string;
  source_document_id: string;
  rationale: string;
}

export async function listTimelineEntries(caseId: string): Promise<TimelineEntry[]> {
  const { data } = await http.get<{ entries: TimelineEntry[] }>(
    `/cases/${caseId}/timeline-entries`,
  );
  return data.entries;
}

export async function createTimelineEntry(caseId: string, body: {
  occurred_at: string;
  label: string;
  notes?: string;
  source_document_id?: string;
  rationale?: string;
  source?: TimelineEntrySource;
}): Promise<TimelineEntry> {
  const { data } = await http.post<TimelineEntry>(`/cases/${caseId}/timeline-entries`, body);
  return data;
}

export async function deleteTimelineEntry(caseId: string, entryId: string): Promise<void> {
  await http.delete(`/cases/${caseId}/timeline-entries/${entryId}`);
}

export async function suggestTimelineEntries(caseId: string): Promise<{
  suggestions: TimelineEntrySuggestion[];
  model?: string;
  reason?: string;
}> {
  const { data } = await http.post(`/cases/${caseId}/timeline-entries/suggestions`);
  return data;
}

// ── Notes (detective freeform scratch) ───────────────────────────────────

export type NoteSubjectKind = "case" | "document" | "report";

export interface Note {
  id: string;
  case_id: string;
  subject_kind: NoteSubjectKind;
  subject_id: string;
  body: string;
  created_by: string;
  created_at: string | null;
  updated_by: string;
  updated_at: string | null;
}

export async function listNotes(
  caseId: string,
  filter?: { subjectKind?: NoteSubjectKind; subjectId?: string },
): Promise<Note[]> {
  const params: Record<string, string> = {};
  if (filter?.subjectKind) params.subject_kind = filter.subjectKind;
  if (filter?.subjectId) params.subject_id = filter.subjectId;
  const { data } = await http.get<{ notes: Note[] }>(
    `/cases/${caseId}/notes`, { params },
  );
  return data.notes;
}

export async function createNote(caseId: string, body: {
  subject_kind: NoteSubjectKind;
  subject_id: string;
  body: string;
}): Promise<Note> {
  const { data } = await http.post<Note>(`/cases/${caseId}/notes`, body);
  return data;
}

export async function updateNote(caseId: string, noteId: string, body: string): Promise<Note> {
  const { data } = await http.patch<Note>(`/cases/${caseId}/notes/${noteId}`, { body });
  return data;
}

export async function deleteNote(caseId: string, noteId: string): Promise<void> {
  await http.delete(`/cases/${caseId}/notes/${noteId}`);
}

// ── Next-step suggestions (Phase C — state-aware) ────────────────────────

export type NextStepCategory =
  | "interview" | "evidence" | "legal"
  | "documentation" | "research" | "other";

export interface NextStepSuggestion {
  step: string;
  category: NextStepCategory;
  rationale: string;
}

export async function suggestNextSteps(caseId: string): Promise<{
  suggestions: NextStepSuggestion[];
  model?: string;
  reason?: string;
}> {
  const { data } = await http.post(`/cases/${caseId}/next-steps/suggestions`);
  return data;
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

export interface ReviseProposal {
  proposed_text: string;
  applies_to: "selection" | "whole_draft";
  model: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
}

export async function reviseReport(
  id: string,
  body: { instruction: string; selected_text?: string },
): Promise<ReviseProposal> {
  const { data } = await http.post<ReviseProposal>(`/reports/${id}/revise`, body, {
    // LLM round-trip can be slow on local models.
    timeout: 180000,
  });
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
