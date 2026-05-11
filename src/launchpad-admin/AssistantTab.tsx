/**
 * Assistant tab — plain-English permission requests, powered by a local LLM.
 *
 * Flow:
 *   1. Admin types "give HR staff ability to edit only HR SOPs"
 *   2. POST /admin/assist returns validated proposed actions
 *   3. Each action renders as a card with its summary, warnings, and an
 *      Apply button (disabled if invalid)
 *   4. Apply calls the existing endpoint (POST /roles | /assignments |
 *      /mappings) — so the same auth, no-escalation, and schema validation
 *      run on every apply. The LLM never bypasses that path.
 *
 * No auto-apply, no batch apply — one click per action.
 */
import { useState } from "react";
import { adminApi } from "./api";
import { usePermission } from "./hooks";
import type { AssistResponse, ProposedAction } from "./types";

const EXAMPLES = [
  "Give HR staff read access to every SOP but only edit access to the HR library",
  "Auto-assign the reviewer role to everyone in AD group Compliance-Reviewers",
  "Create a role called 'tag_manager' that can only manage tags",
  "Make IT department users able to edit the IT library",
];

type ActionStatus = "idle" | "applying" | "applied" | "error";

export function AssistantTab() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AssistResponse | null>(null);
  const [actionStatus, setActionStatus] = useState<Record<number, { s: ActionStatus; msg?: string }>>({});
  const canManage = usePermission("roles.manage");

  if (!canManage) {
    return <div style={{ padding: 16 }}>You need the "Manage roles" capability to use the assistant.</div>;
  }

  const run = async (text?: string) => {
    const p = (text ?? prompt).trim();
    if (!p) return;
    setPrompt(p);
    setLoading(true);
    setResult(null);
    setActionStatus({});
    try {
      const r = await adminApi.assist(p);
      setResult(r);
    } catch (e) {
      setResult({
        understanding: "",
        actions: [],
        questions: [],
        notes: "",
        model: "",
        error: (e as Error).message,
      });
    } finally {
      setLoading(false);
    }
  };

  const apply = async (idx: number, action: ProposedAction) => {
    setActionStatus((s) => ({ ...s, [idx]: { s: "applying" } }));
    try {
      if (action.kind === "create_role") {
        await adminApi.createRole(action.body as any);
      } else if (action.kind === "assign_role") {
        await adminApi.createAssignment(action.body as any);
      } else if (action.kind === "create_mapping") {
        await adminApi.createMapping(action.body as any);
      } else {
        throw new Error(`Unknown action kind: ${action.kind}`);
      }
      setActionStatus((s) => ({ ...s, [idx]: { s: "applied" } }));
    } catch (e) {
      setActionStatus((s) => ({ ...s, [idx]: { s: "error", msg: (e as Error).message } }));
    }
  };

  return (
    <div style={{ padding: 16, maxWidth: 780 }}>
      <h2 style={{ margin: "0 0 4px 0" }}>Permission assistant</h2>
      <p style={{ margin: "0 0 16px 0", color: "#666", fontSize: "0.8125rem" }}>
        Describe what access you want in plain English. The assistant proposes
        concrete actions — you review each one and click Apply. Runs locally
        via Ollama; nothing is sent to an external service.
      </p>

      {/* ── Prompt box ─────────────────────────────────────────────── */}
      <textarea
        style={promptBox}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="e.g. Give HR read access everywhere and edit only in the HR library"
        rows={3}
        disabled={loading}
      />
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
        <button onClick={() => run()} disabled={loading || !prompt.trim()} style={primaryBtn}>
          {loading ? "Thinking…" : "Propose actions"}
        </button>
        <span style={{ fontSize: "0.75rem", color: "#666" }}>
          {result?.model && `model: ${result.model}`}
        </span>
      </div>

      {/* ── Examples when idle ─────────────────────────────────────── */}
      {!loading && !result && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: "0.75rem", color: "#666", marginBottom: 6 }}>Try one of these:</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {EXAMPLES.map((ex) => (
              <button key={ex} onClick={() => run(ex)} style={exampleBtn}>
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Error ──────────────────────────────────────────────────── */}
      {result?.error && (
        <div style={errorBox}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Assistant error</div>
          <div style={{ fontSize: "0.8125rem" }}>{result.error}</div>
          <div style={{ fontSize: "0.75rem", color: "#555", marginTop: 8 }}>
            If Ollama isn't running, start it with <code>ollama serve</code>.
            If the model isn't pulled, run <code>ollama pull &lt;model&gt;</code>{" "}
            (configurable via the <code>ADMIN_ASSISTANT_MODEL</code> env var on the backend).
          </div>
        </div>
      )}

      {/* ── Understanding ──────────────────────────────────────────── */}
      {result && !result.error && (
        <>
          {result.understanding && (
            <div style={understandingBox}>
              <div style={{ fontWeight: 700, fontSize: "0.75rem", marginBottom: 4 }}>
                🤖 Here's what I understood:
              </div>
              <div style={{ fontSize: "0.875rem" }}>{result.understanding}</div>
            </div>
          )}

          {result.reviewer_ran && result.reviewer_summary && (
            <div style={reviewerBox}>
              <div style={{ fontWeight: 700, fontSize: "0.75rem", marginBottom: 4 }}>
                🔍 Reviewer pass{result.reviewer_model ? ` · ${result.reviewer_model}` : ""}:
              </div>
              <div style={{ fontSize: "0.8125rem" }}>{result.reviewer_summary}</div>
            </div>
          )}

          {/* Clarifying questions — either agent can ask. */}
          {result.questions && result.questions.length > 0 && (
            <div style={questionsBox}>
              <div style={{ fontWeight: 700, fontSize: "0.75rem", marginBottom: 6 }}>
                ❓ Before acting, the assistant needs to know:
              </div>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: "0.875rem", lineHeight: 1.6 }}>
                {result.questions.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
              <div style={{ fontSize: "0.75rem", color: "#666", marginTop: 8 }}>
                Add the answers to your prompt above and re-run for a more confident proposal.
              </div>
            </div>
          )}

          {result.notes && (
            <div style={notesBox}>
              <div style={{ fontWeight: 600, fontSize: "0.75rem", marginBottom: 4 }}>Notes</div>
              <div style={{ fontSize: "0.8125rem" }}>{result.notes}</div>
            </div>
          )}

          {/* ── Proposed actions ──────────────────────────────────── */}
          {result.actions.length === 0 ? (
            <div style={{ marginTop: 16, color: "#888", fontSize: "0.875rem" }}>
              {result.questions && result.questions.length > 0
                ? "No actions proposed yet — answer the questions above and re-run."
                : "No actions proposed. Try being more specific, or start from an example above."}
            </div>
          ) : (
            <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
              {result.actions.map((a, idx) => (
                <ActionCard
                  key={idx}
                  action={a}
                  status={actionStatus[idx]?.s ?? "idle"}
                  errorMsg={actionStatus[idx]?.msg}
                  onApply={() => apply(idx, a)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ActionCard({
  action, status, errorMsg, onApply,
}: {
  action: ProposedAction;
  status: ActionStatus;
  errorMsg?: string;
  onApply: () => void;
}) {
  const kindEmoji =
    action.kind === "create_role" ? "🎭"
    : action.kind === "assign_role" ? "👤"
    : action.kind === "create_mapping" ? "🔗"
    : "❓";
  const kindLabel =
    action.kind === "create_role" ? "Create role"
    : action.kind === "assign_role" ? "Assign role"
    : action.kind === "create_mapping" ? "Auto-assignment rule"
    : "Unknown action";

  const verdict = action.review_verdict || "approved";
  const rejected = verdict === "rejected";
  const canApply = action.valid && !rejected && status !== "applying" && status !== "applied";
  const [showDetails, setShowDetails] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  const verdictMeta: Record<string, { label: string; bg: string; color: string; emoji: string }> = {
    approved: { label: "Reviewer approved", bg: "#dcfce7", color: "#166534", emoji: "✓" },
    modified: { label: "Reviewer modified", bg: "#fef3c7", color: "#92400e", emoji: "✎" },
    rejected: { label: "Reviewer rejected", bg: "#fee2e2", color: "#991b1b", emoji: "🚫" },
    added:    { label: "Reviewer added", bg: "#dbeafe", color: "#1e40af", emoji: "+" },
  };
  const v = verdictMeta[verdict] ?? verdictMeta.approved!;

  const cardBorder = status === "applied" ? "#22c55e"
    : rejected ? "#fca5a5"
    : !action.valid ? "#fca5a5"
    : verdict === "modified" ? "#fbbf24"
    : verdict === "added" ? "#60a5fa"
    : "#e5e7eb";

  return (
    <div style={{ ...card, borderColor: cardBorder }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <span style={{ fontSize: "1.25rem" }}>{kindEmoji}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", opacity: 0.6, letterSpacing: "0.04em", fontWeight: 700 }}>
              {kindLabel}
            </div>
            <span style={{ ...verdictBadge, background: v.bg, color: v.color }}>
              {v.emoji} {v.label}
            </span>
          </div>
          <div style={{ fontSize: "0.9375rem", marginTop: 4, fontWeight: 500 }}>{action.summary}</div>

          {/* Reviewer explanation */}
          {action.review_notes && (
            <div style={reviewerNotes}>
              🔍 <strong>Reviewer:</strong> {action.review_notes}
            </div>
          )}

          {/* Original disclosure when reviewer changed or killed the proposer's version */}
          {(verdict === "modified" || verdict === "rejected") && action.original_summary && (
            <>
              <button onClick={() => setShowOriginal(!showOriginal)} style={linkBtn}>
                {showOriginal ? "Hide" : "Show"} what the proposer originally drafted
              </button>
              {showOriginal && (
                <div style={originalBox}>
                  <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", opacity: 0.6, fontWeight: 700, marginBottom: 4 }}>
                    Proposer's draft (replaced by reviewer)
                  </div>
                  <div style={{ fontSize: "0.8125rem" }}>{action.original_summary}</div>
                </div>
              )}
            </>
          )}

          {action.warnings.length > 0 && (
            <ul style={warningList}>
              {action.warnings.map((w, i) => (
                <li key={i}>⚠️ {w}</li>
              ))}
            </ul>
          )}

          {status === "applied" && (
            <div style={{ color: "#16a34a", fontSize: "0.8125rem", marginTop: 6 }}>
              ✓ Applied
            </div>
          )}
          {status === "error" && (
            <div style={{ color: "#dc2626", fontSize: "0.8125rem", marginTop: 6 }}>
              ✗ {errorMsg}
            </div>
          )}

          {showDetails && (
            <pre style={detailsBox}>
              {JSON.stringify(action.body, null, 2)}
            </pre>
          )}
          <button
            onClick={() => setShowDetails(!showDetails)}
            style={linkBtn}
          >
            {showDetails ? "Hide" : "Show"} payload
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <button
            onClick={onApply}
            disabled={!canApply}
            style={canApply ? primaryBtn : disabledBtn}
            title={rejected ? "Rejected by reviewer — not appliable" : undefined}
          >
            {status === "applying" ? "Applying…" : status === "applied" ? "Applied" : rejected ? "Rejected" : "Apply"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── styles ──
const promptBox: React.CSSProperties = {
  width: "100%", padding: 10, border: "1px solid #d1d5db", borderRadius: 8,
  fontSize: "0.9375rem", fontFamily: "inherit", resize: "vertical", boxSizing: "border-box",
};
const primaryBtn: React.CSSProperties = {
  padding: "8px 16px", background: "#2563eb", color: "#fff", border: "none",
  borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: "0.8125rem",
};
const disabledBtn: React.CSSProperties = {
  ...primaryBtn, background: "#cbd5e1", cursor: "not-allowed",
};
const exampleBtn: React.CSSProperties = {
  textAlign: "left", padding: "8px 12px", background: "#f8fafc",
  border: "1px solid #e2e8f0", borderRadius: 6, cursor: "pointer",
  fontSize: "0.8125rem", color: "#334155",
};
const understandingBox: React.CSSProperties = {
  marginTop: 16, padding: "12px 14px",
  background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8,
};
const reviewerBox: React.CSSProperties = {
  marginTop: 8, padding: "10px 14px",
  background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8,
};
const questionsBox: React.CSSProperties = {
  marginTop: 10, padding: "12px 14px",
  background: "#fefce8", border: "1px solid #fde68a", borderRadius: 8,
};
const verdictBadge: React.CSSProperties = {
  padding: "2px 8px", borderRadius: 10, fontSize: "0.6875rem", fontWeight: 700,
};
const reviewerNotes: React.CSSProperties = {
  marginTop: 6, padding: "6px 10px",
  background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6,
  fontSize: "0.8125rem", color: "#334155",
};
const originalBox: React.CSSProperties = {
  marginTop: 6, padding: 8,
  background: "#fafaf9", border: "1px dashed #d6d3d1", borderRadius: 6,
  textDecoration: "line-through", color: "#78716c",
};
const notesBox: React.CSSProperties = {
  marginTop: 10, padding: "10px 12px",
  background: "#fffbeb", border: "1px solid #fde68a", borderRadius: 6,
};
const errorBox: React.CSSProperties = {
  marginTop: 16, padding: 12,
  background: "#fee2e2", border: "1px solid #fecaca", borderRadius: 8,
  color: "#991b1b",
};
const card: React.CSSProperties = {
  padding: 14, background: "#fff", border: "1px solid #e5e7eb",
  borderRadius: 10, boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
};
const warningList: React.CSSProperties = {
  margin: "8px 0 0 0", padding: "0 0 0 16px", fontSize: "0.75rem", color: "#92400e",
};
const detailsBox: React.CSSProperties = {
  marginTop: 8, padding: 8, background: "#f8fafc", borderRadius: 4,
  fontSize: "0.6875rem", maxHeight: 200, overflow: "auto", fontFamily: "ui-monospace, monospace",
};
const linkBtn: React.CSSProperties = {
  marginTop: 4, padding: 0, background: "none", border: "none",
  color: "#2563eb", cursor: "pointer", fontSize: "0.75rem", textDecoration: "underline",
};
