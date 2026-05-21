// Hypothesis tab — voice/text brain dump → AI structured hypotheses →
// detective-approved investigation list with cross-check findings.
//
// Phase 1: typed input only. Voice capture + audio upload land in Phase 2
// behind the same backend endpoints (BrainDump model carries the source).

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  acceptHypothesisFinding, checkHypothesis, createBrainDump, createHypothesis,
  deleteHypothesis, generateDeNovoHypotheses, getBiasVocab, listHypotheses,
  redTeamHypothesis, suggestHypotheses, updateBrainDump,
  updateHypothesis, uploadAudioBrainDump,
  type BiasFlagDef, type BrainDump, type Hypothesis, type HypothesisFinding,
  type HypothesisFindingKind, type HypothesisOrigin, type HypothesisStatus,
  type HypothesisSuggestion, type RedTeamResult,
} from "@/lib/api/coldcase";


const STATUS_LABELS: Record<HypothesisStatus, string> = {
  investigating: "Investigating",
  confirmed: "Confirmed",
  disproved: "Disproved",
  superseded: "Superseded",
};

const STATUS_CHIP_CLS: Record<HypothesisStatus, string> = {
  investigating: "bg-blue-50 text-blue-800 border-blue-200",
  confirmed: "bg-emerald-50 text-emerald-800 border-emerald-200",
  disproved: "bg-red-50 text-red-800 border-red-200",
  superseded: "bg-slate-100 text-slate-700 border-slate-300",
};

const FINDING_CHIP_CLS: Record<HypothesisFindingKind, string> = {
  supporting: "bg-emerald-50 text-emerald-800 border-emerald-200",
  contradicting: "bg-red-50 text-red-800 border-red-200",
  gap: "bg-amber-50 text-amber-800 border-amber-200",
};

const ORIGIN_LABEL: Record<HypothesisOrigin, string> = {
  human_typed: "Human",
  ai_from_braindump: "AI · brain dump",
  ai_de_novo: "AI · de-novo",
  ai_alternative: "AI · alternative",
};

const ORIGIN_CHIP_CLS: Record<HypothesisOrigin, string> = {
  human_typed: "bg-slate-100 text-slate-700 border-slate-300",
  ai_from_braindump: "bg-indigo-50 text-indigo-800 border-indigo-200",
  ai_de_novo: "bg-teal-50 text-teal-800 border-teal-200",
  ai_alternative: "bg-purple-50 text-purple-800 border-purple-200",
};


export default function HypothesisTab({ caseId }: { caseId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["case-hypotheses", caseId],
    queryFn: () => listHypotheses(caseId),
    staleTime: 30_000,
  });

  const hypotheses = data?.hypotheses ?? [];
  const grouped = useMemo(() => {
    const active = hypotheses.filter((h) => h.status === "investigating");
    const closed = hypotheses.filter((h) => h.status !== "investigating");
    return { active, closed };
  }, [hypotheses]);

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="max-w-4xl space-y-6">
        <header>
          <h2 className="text-[15px] font-semibold text-slate-900">Hypotheses</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Three AI agents with different incentives. <b>Generator</b> hones a
            brain dump into structured hypotheses. <b>De-novo</b> reads the case
            docs without your framing for a fresh-eyes view. <b>Red-team</b>
            attacks each hypothesis on demand — counter-evidence, alternatives,
            cognitive bias flags. Detective approves every step.
          </p>
        </header>

        <BrainDumpComposer caseId={caseId} />
        <DeNovoGenerator caseId={caseId} />

        <section>
          <h3 className="text-[13px] font-semibold text-slate-900 mb-2">
            Investigating ({grouped.active.length})
          </h3>
          {isLoading ? (
            <div className="text-xs text-slate-500">Loading…</div>
          ) : grouped.active.length === 0 ? (
            <div className="border border-dashed border-slate-300 rounded p-6 text-center text-xs text-slate-500">
              No active hypotheses. Capture a brain dump above and approve the AI's
              proposals to start investigating.
            </div>
          ) : (
            <ul className="space-y-3">
              {grouped.active.map((h) => <HypothesisCard key={h.id} caseId={caseId} hypothesis={h} />)}
            </ul>
          )}
        </section>

        {grouped.closed.length > 0 ? (
          <section>
            <h3 className="text-[13px] font-semibold text-slate-900 mb-2">
              Closed ({grouped.closed.length})
            </h3>
            <ul className="space-y-3 opacity-80">
              {grouped.closed.map((h) => <HypothesisCard key={h.id} caseId={caseId} hypothesis={h} />)}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  );
}


// ── Brain-dump composer + suggestion review ──────────────────────────────

type Mode = "type" | "record" | "upload";


function BrainDumpComposer({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<Mode>("type");

  // The composer's persistent state — the active brain-dump, its transcript
  // (editable after audio transcribes), and the AI suggestion review state.
  const [activeDump, setActiveDump] = useState<BrainDump | null>(null);
  const [transcript, setTranscript] = useState("");
  const [suggestions, setSuggestions] = useState<HypothesisSuggestion[]>([]);
  const [model, setModel] = useState("");
  const [accepted, setAccepted] = useState<string[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [errorMsg, setErrorMsg] = useState("");

  const textDumpMut = useMutation({
    mutationFn: (text: string) => createBrainDump(caseId, { transcript: text }),
  });
  const audioDumpMut = useMutation({
    mutationFn: (vars: { blob: Blob; filename: string; source: "audio_recorded" | "audio_uploaded" }) =>
      uploadAudioBrainDump(caseId, vars.blob, vars.filename, vars.source),
  });
  const editTranscriptMut = useMutation({
    mutationFn: (vars: { id: string; text: string }) =>
      updateBrainDump(caseId, vars.id, { transcript: vars.text }),
  });

  const suggestMut = useMutation({
    mutationFn: (id: string) => suggestHypotheses(caseId, id),
    onSuccess: (resp) => {
      setSuggestions(resp.suggestions);
      setModel(resp.model ?? "");
      setAccepted([]);
      setDismissed(new Set());
    },
  });

  const acceptMut = useMutation({
    mutationFn: (s: HypothesisSuggestion) => createHypothesis(caseId, {
      title: s.title,
      body: s.body,
      rationale: s.rationale,
      brain_dump_id: activeDump?.id,
      model,
    }),
    onSuccess: (_h, s) => {
      qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] });
      setAccepted((p) => p.includes(s.title) ? p : [...p, s.title]);
    },
  });

  const reset = () => {
    setActiveDump(null);
    setTranscript("");
    setSuggestions([]);
    setAccepted([]);
    setDismissed(new Set());
    setErrorMsg("");
  };

  const onTypedCapture = async () => {
    const text = transcript.trim();
    if (!text) return;
    setErrorMsg("");
    try {
      const dump = await textDumpMut.mutateAsync(text);
      setActiveDump(dump);
      suggestMut.mutate(dump.id);
    } catch (err) {
      setErrorMsg((err as Error).message);
    }
  };

  const handleAudioCapture = async (
    blob: Blob, filename: string, source: "audio_recorded" | "audio_uploaded",
  ) => {
    setErrorMsg("");
    try {
      const dump = await audioDumpMut.mutateAsync({ blob, filename, source });
      setActiveDump(dump);
      setTranscript(dump.transcript);
      if (dump.transcript) {
        // Don't auto-suggest yet — let detective edit Whisper's output first.
      }
    } catch (err) {
      setErrorMsg((err as Error).message);
    }
  };

  const runSuggestOnExistingDump = async () => {
    if (!activeDump) return;
    setErrorMsg("");
    try {
      // If transcript changed, persist it before re-extracting.
      if (transcript.trim() !== activeDump.transcript) {
        const updated = await editTranscriptMut.mutateAsync({
          id: activeDump.id, text: transcript.trim(),
        });
        setActiveDump(updated);
      }
      suggestMut.mutate(activeDump.id);
    } catch (err) {
      setErrorMsg((err as Error).message);
    }
  };

  const visibleSuggestions = suggestions.filter(
    (s) => !accepted.includes(s.title) && !dismissed.has(s.title),
  );

  const isBusy = textDumpMut.isPending || audioDumpMut.isPending || suggestMut.isPending || editTranscriptMut.isPending;

  return (
    <section className="border border-indigo-200 bg-indigo-50/30 rounded p-4">
      <div className="flex items-baseline justify-between mb-2 gap-2">
        <div>
          <h3 className="text-[13px] font-semibold text-slate-900">Brain dump → hypotheses</h3>
          <p className="text-[11px] text-slate-500">
            Speak freely, upload a voice memo, or type. AI structures the dump
            into falsifiable hypotheses you approve individually.
          </p>
        </div>
        <ModeSwitch mode={mode} setMode={setMode} disabled={Boolean(activeDump)} />
      </div>

      {/* Input panel — three flavors. Hidden once we have a transcript to
          edit; the transcript editor takes over. */}
      {!activeDump ? (
        <>
          {mode === "type" ? (
            <textarea
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              rows={5}
              placeholder={"Driving back from the witness interview. Two things bug me. First, the timeline doesn't add up..."}
              className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm bg-white"
            />
          ) : null}
          {mode === "record" ? (
            <VoiceRecorder
              onCapture={(blob, filename) => handleAudioCapture(blob, filename, "audio_recorded")}
              disabled={isBusy}
            />
          ) : null}
          {mode === "upload" ? (
            <AudioUploadDrop
              onFile={(file) => handleAudioCapture(file, file.name, "audio_uploaded")}
              disabled={isBusy}
            />
          ) : null}
        </>
      ) : null}

      {/* Once we have an active dump with a transcript, show the editor +
          a single "extract hypotheses" button. */}
      {activeDump ? (
        <>
          <div className="text-[11px] text-slate-500 mb-1.5 flex items-baseline justify-between">
            <span>
              Transcript {activeDump.transcript_model ? (
                <span className="font-mono">· {activeDump.transcript_model}</span>
              ) : null}
              {activeDump.audio_filename ? (
                <span className="font-mono"> · {activeDump.audio_filename}</span>
              ) : null}
            </span>
            <span className="text-slate-400">Edit before extracting — fix names, dates, badge numbers.</span>
          </div>
          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            rows={Math.min(12, Math.max(4, Math.ceil(transcript.length / 90)))}
            className="w-full border border-slate-300 rounded px-2 py-1.5 text-sm bg-white"
          />
        </>
      ) : null}

      <div className="flex items-center gap-2 mt-2">
        {!activeDump && mode === "type" ? (
          <button
            type="button"
            disabled={!transcript.trim() || isBusy}
            onClick={onTypedCapture}
            className="px-3 py-1.5 text-xs rounded bg-indigo-700 text-white hover:bg-indigo-800 disabled:opacity-50"
          >
            {isBusy ? "Reading…" : "Capture + suggest hypotheses"}
          </button>
        ) : null}
        {activeDump ? (
          <>
            <button
              type="button"
              disabled={!transcript.trim() || isBusy}
              onClick={runSuggestOnExistingDump}
              className="px-3 py-1.5 text-xs rounded bg-indigo-700 text-white hover:bg-indigo-800 disabled:opacity-50"
            >
              {isBusy ? "Reading…" : suggestions.length > 0 ? "Refresh hypotheses" : "Suggest hypotheses"}
            </button>
            <button
              type="button"
              onClick={reset}
              className="px-2 py-1 text-xs rounded border border-slate-300 hover:bg-slate-50"
            >
              New dump
            </button>
          </>
        ) : null}
      </div>

      {accepted.length > 0 ? (
        <div className="text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-2 py-1 mt-2">
          ✓ {accepted.length} hypothesis{accepted.length === 1 ? "" : "es"} under investigation — see list below.
        </div>
      ) : null}

      {errorMsg ? <div className="text-xs text-red-700 mt-2">{errorMsg}</div> : null}
      {suggestMut.error ? (
        <div className="text-xs text-red-700 mt-2">{(suggestMut.error as Error).message}</div>
      ) : null}

      {visibleSuggestions.length > 0 ? (
        <ul className="space-y-2 mt-3">
          {visibleSuggestions.map((s) => {
            const isPending = acceptMut.isPending && acceptMut.variables?.title === s.title;
            return (
              <li key={s.title} className="bg-white border border-slate-200 rounded p-2.5">
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-slate-900">{s.title}</div>
                    {s.body ? <div className="text-xs text-slate-700 mt-0.5 leading-snug">{s.body}</div> : null}
                    {s.rationale ? <div className="text-[11px] text-indigo-700 italic mt-1">{s.rationale}</div> : null}
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => acceptMut.mutate(s)}
                      className="px-2 py-0.5 text-[11px] rounded bg-indigo-700 text-white hover:bg-indigo-800 disabled:opacity-50"
                    >
                      {isPending ? "Saving…" : "Investigate"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setDismissed((p) => new Set(p).add(s.title))}
                      className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}


function ModeSwitch({
  mode, setMode, disabled,
}: { mode: Mode; setMode: (m: Mode) => void; disabled: boolean }) {
  const opts: { id: Mode; label: string }[] = [
    { id: "type", label: "Type" },
    { id: "record", label: "Record" },
    { id: "upload", label: "Upload" },
  ];
  return (
    <div className="flex border border-slate-300 rounded overflow-hidden shrink-0 text-[11px]">
      {opts.map((o) => (
        <button
          key={o.id}
          type="button"
          disabled={disabled}
          onClick={() => setMode(o.id)}
          className={
            "px-2 py-0.5 " +
            (mode === o.id
              ? "bg-indigo-700 text-white"
              : "bg-white text-slate-700 hover:bg-slate-50") +
            (disabled ? " opacity-50 cursor-not-allowed" : "")
          }
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}


// ── In-portal voice recorder via MediaRecorder ────────────────────────────
// Browser-native: no extra dependencies. Records to WebM/Opus by default
// (Chrome / Edge / Firefox); Safari falls back to mp4/aac.

function VoiceRecorder({
  onCapture, disabled,
}: {
  onCapture: (blob: Blob, filename: string) => void;
  disabled: boolean;
}) {
  const [state, setState] = useState<"idle" | "requesting" | "recording" | "uploading">("idle");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
    }
  }, []);

  const start = async () => {
    setError("");
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("Browser does not support audio recording. Use Upload instead.");
      return;
    }
    try {
      setState("requesting");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      chunksRef.current = [];
      mr.ondataavailable = (ev) => { if (ev.data.size > 0) chunksRef.current.push(ev.data); };
      mr.onstop = async () => {
        const mime = mr.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: mime });
        const ext = mime.includes("mp4") ? "mp4"
          : mime.includes("ogg") ? "ogg"
          : "webm";
        const filename = `brain-dump-${new Date().toISOString().replace(/[:.]/g, "-")}.${ext}`;
        stream.getTracks().forEach((t) => t.stop());
        setState("uploading");
        try {
          await onCapture(blob, filename);
        } finally {
          setState("idle");
          setElapsed(0);
        }
      };
      mr.start();
      startedAtRef.current = Date.now();
      setElapsed(0);
      intervalRef.current = setInterval(() => {
        setElapsed(Math.round((Date.now() - startedAtRef.current) / 1000));
      }, 250);
      setState("recording");
    } catch (err) {
      setError((err as Error).message || "Could not access microphone.");
      setState("idle");
    }
  };

  const stop = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    mediaRecorderRef.current?.stop();
  };

  const mmss = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;

  return (
    <div className="border border-dashed border-slate-300 rounded p-6 bg-white text-center">
      {state === "idle" ? (
        <>
          <button
            type="button"
            disabled={disabled}
            onClick={start}
            className="px-4 py-2 text-sm rounded-full bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
          >
            ● Start recording
          </button>
          <div className="text-[11px] text-slate-500 mt-2">
            Browser will ask for microphone permission. Recording stays local until
            you stop; on stop it's uploaded, stored with the case, and transcribed.
          </div>
        </>
      ) : null}
      {state === "requesting" ? (
        <div className="text-sm text-slate-700">Requesting microphone…</div>
      ) : null}
      {state === "recording" ? (
        <>
          <button
            type="button"
            onClick={stop}
            className="px-4 py-2 text-sm rounded-full bg-slate-800 text-white hover:bg-slate-900"
          >
            ■ Stop ({mmss})
          </button>
          <div className="text-[11px] text-red-700 mt-2 animate-pulse">● Recording</div>
        </>
      ) : null}
      {state === "uploading" ? (
        <div className="text-sm text-slate-700">Uploading + transcribing…</div>
      ) : null}
      {error ? <div className="text-xs text-red-700 mt-2">{error}</div> : null}
    </div>
  );
}


// ── Drag-drop audio upload ────────────────────────────────────────────────

function AudioUploadDrop({
  onFile, disabled,
}: {
  onFile: (file: File) => void;
  disabled: boolean;
}) {
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (disabled) return;
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={
        "border-2 border-dashed rounded p-6 text-center bg-white " +
        (over ? "border-indigo-400 bg-indigo-50/40" : "border-slate-300") +
        (disabled ? " opacity-50" : "")
      }
    >
      <div className="text-sm text-slate-700">Drop a voice memo here</div>
      <div className="text-[11px] text-slate-500 mt-1">
        .m4a (iPhone Voice Memos), .mp3, .wav, .webm, .ogg — max 50 MB
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="mt-2 px-3 py-1 text-xs rounded border border-indigo-300 bg-white text-indigo-800 hover:bg-indigo-50 disabled:opacity-50"
      >
        Choose file…
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="audio/*,.m4a,.mp3,.wav,.webm,.ogg"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          if (inputRef.current) inputRef.current.value = "";
        }}
      />
    </div>
  );
}


// ── A single hypothesis with status + findings + check button ────────────

function HypothesisCard({ caseId, hypothesis: h }: { caseId: string; hypothesis: Hypothesis }) {
  const qc = useQueryClient();
  const [checking, setChecking] = useState(false);
  const [pendingFindings, setPendingFindings] = useState<(Omit<HypothesisFinding, "accepted_by" | "accepted_at" | "suggested_by_model"> & { _key: string })[]>([]);
  const [checkModel, setCheckModel] = useState("");
  const [error, setError] = useState<string>("");
  const [redTeamResult, setRedTeamResult] = useState<RedTeamResult | null>(null);
  const [redTeaming, setRedTeaming] = useState(false);

  const statusMut = useMutation({
    mutationFn: (status: HypothesisStatus) => updateHypothesis(caseId, h.id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] }),
  });
  const deleteMut = useMutation({
    mutationFn: () => deleteHypothesis(caseId, h.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] }),
  });
  const acceptFindingMut = useMutation({
    mutationFn: (f: typeof pendingFindings[number]) => acceptHypothesisFinding(caseId, h.id, {
      kind: f.kind, excerpt: f.excerpt, rationale: f.rationale,
      source_doc_id: f.source_doc_id, source_doc_filename: f.source_doc_filename,
      model: checkModel,
    }),
    onSuccess: (_data, f) => {
      qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] });
      setPendingFindings((prev) => prev.filter((p) => p._key !== f._key));
    },
  });
  const acceptAltMut = useMutation({
    mutationFn: (alt: HypothesisSuggestion) => createHypothesis(caseId, {
      title: alt.title,
      body: alt.body,
      rationale: alt.rationale,
      origin: "ai_alternative",
      parent_hypothesis_id: h.id,
      model: redTeamResult?.model ?? "",
    }),
    onSuccess: (_data, alt) => {
      qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] });
      setRedTeamResult((prev) => prev ? {
        ...prev,
        alternatives: prev.alternatives.filter((a) => a.title !== alt.title),
      } : prev);
    },
  });

  const runCheck = async () => {
    setError("");
    setChecking(true);
    try {
      const resp = await checkHypothesis(caseId, h.id);
      setCheckModel(resp.model ?? "");
      setPendingFindings(resp.findings.map((f, i) => ({ ...f, _key: `${f.kind}-${i}-${f.excerpt.slice(0, 12)}` })));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setChecking(false);
    }
  };

  const runRedTeam = async () => {
    setError("");
    setRedTeaming(true);
    try {
      const resp = await redTeamHypothesis(caseId, h.id);
      setRedTeamResult(resp);
      // The endpoint persists bias_flags + logical_gaps on the hypothesis;
      // refresh so the card reflects the new chips.
      qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRedTeaming(false);
    }
  };

  return (
    <li className="border border-slate-200 rounded p-3 bg-white">
      <header className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] capitalize shrink-0 ${STATUS_CHIP_CLS[h.status]}`}>
              {STATUS_LABELS[h.status]}
            </span>
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] shrink-0 ${ORIGIN_CHIP_CLS[h.origin]}`}>
              {ORIGIN_LABEL[h.origin]}
            </span>
            <h4 className="text-sm font-semibold text-slate-900">{h.title}</h4>
            {h.red_team_count > 0 ? (
              <span className="text-[10px] text-amber-700" title="Times red-teamed">
                ⚠ {h.red_team_count}× challenged
              </span>
            ) : null}
          </div>
          {h.body ? <p className="text-xs text-slate-700 mt-1 leading-relaxed">{h.body}</p> : null}
          {h.rationale ? (
            <p className="text-[11px] text-slate-500 italic mt-1">Rationale: {h.rationale}</p>
          ) : null}
          {h.origin === "ai_alternative" && h.parent_hypothesis_id ? (
            <p className="text-[11px] text-purple-700 mt-1">
              ↗ alternative surfaced by red-teaming a parent hypothesis
            </p>
          ) : null}
          {h.bias_flags.length > 0 ? (
            <BiasFlagChips slugs={h.bias_flags} />
          ) : null}
          {h.logical_gaps.length > 0 ? (
            <div className="text-[11px] text-amber-800 mt-1.5 pl-2 border-l-2 border-amber-200 space-y-0.5">
              <div className="text-[10px] uppercase tracking-wide text-amber-700 font-semibold">Logical gaps</div>
              {h.logical_gaps.map((g, i) => <div key={i}>{g}</div>)}
            </div>
          ) : null}
        </div>
        <div className="shrink-0">
          <select
            value={h.status}
            onChange={(e) => statusMut.mutate(e.target.value as HypothesisStatus)}
            className="text-[11px] border border-slate-300 rounded px-1.5 py-0.5 bg-white"
          >
            <option value="investigating">Investigating</option>
            <option value="confirmed">Confirmed</option>
            <option value="disproved">Disproved</option>
            <option value="superseded">Superseded</option>
          </select>
        </div>
      </header>

      {/* Accepted findings */}
      {h.findings.length > 0 ? (
        <div className="mt-2 pt-2 border-t border-slate-100 space-y-1.5">
          <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold">
            Findings on file ({h.findings.length})
          </div>
          {h.findings.map((f, i) => <FindingRow key={i} finding={f} />)}
        </div>
      ) : null}

      {/* Action row */}
      <div className="mt-2 pt-2 border-t border-slate-100">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[11px] text-slate-500">
            Cross-check finds supporting / contradicting / gap evidence. Challenge runs
            the red-team agent — counter-evidence + alternatives + bias flags.
          </span>
          <div className="flex gap-1.5 shrink-0">
            <button
              type="button"
              onClick={runCheck}
              disabled={checking || redTeaming}
              className="px-2.5 py-0.5 text-[11px] rounded border border-blue-300 bg-white text-blue-800 hover:bg-blue-50 disabled:opacity-50"
            >
              {checking ? "Checking…" : "Check evidence"}
            </button>
            <button
              type="button"
              onClick={runRedTeam}
              disabled={checking || redTeaming}
              className="px-2.5 py-0.5 text-[11px] rounded border border-amber-400 bg-white text-amber-900 hover:bg-amber-50 disabled:opacity-50"
            >
              {redTeaming ? "Red-teaming…" : "Challenge this"}
            </button>
            <button
              type="button"
              onClick={() => { if (confirm(`Delete hypothesis "${h.title}"?`)) deleteMut.mutate(); }}
              className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
            >
              Delete
            </button>
          </div>
        </div>

        {error ? <div className="text-[11px] text-red-700 mt-1">{error}</div> : null}

        {pendingFindings.length > 0 ? (
          <ul className="space-y-1.5 mt-2">
            {pendingFindings.map((f) => {
              const isPending = acceptFindingMut.isPending && acceptFindingMut.variables?._key === f._key;
              return (
                <li key={f._key} className="border border-slate-200 rounded p-2 bg-slate-50/60">
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full border text-[10px] capitalize ${FINDING_CHIP_CLS[f.kind]}`}>
                          {f.kind}
                        </span>
                        {f.source_doc_filename ? (
                          <span className="text-[10px] text-slate-500 font-mono">{f.source_doc_filename}</span>
                        ) : null}
                      </div>
                      {f.excerpt ? (
                        <div className="text-[11px] text-slate-800 mt-1 pl-2 border-l-2 border-slate-200">
                          "{f.excerpt}"
                        </div>
                      ) : null}
                      {f.rationale ? (
                        <div className="text-[11px] text-slate-600 italic mt-0.5">{f.rationale}</div>
                      ) : null}
                    </div>
                    <div className="flex flex-col gap-1 shrink-0">
                      <button
                        type="button"
                        disabled={isPending}
                        onClick={() => acceptFindingMut.mutate(f)}
                        className="px-2 py-0.5 text-[11px] rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {isPending ? "Saving…" : "Add to record"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setPendingFindings((p) => p.filter((x) => x._key !== f._key))}
                        className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                      >
                        Skip
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : null}

        {redTeamResult ? (
          <RedTeamResultPanel
            caseId={caseId}
            hypothesis={h}
            result={redTeamResult}
            onAcceptCounter={(f) => {
              acceptFindingMut.mutate({ ...f, _key: `rt-${f.excerpt.slice(0, 16)}` });
              setRedTeamResult((prev) => prev ? {
                ...prev,
                counter_evidence: prev.counter_evidence.filter((c) => c.excerpt !== f.excerpt),
              } : prev);
            }}
            onInvestigateAlt={(alt) => acceptAltMut.mutate(alt)}
            acceptAltPending={(alt) => acceptAltMut.isPending && acceptAltMut.variables?.title === alt.title}
            onDismiss={() => setRedTeamResult(null)}
          />
        ) : null}
      </div>
    </li>
  );
}


// ── Red-team result panel — three-column challenge view ──────────────────

function RedTeamResultPanel({
  result, onAcceptCounter, onInvestigateAlt, acceptAltPending, onDismiss,
}: {
  caseId: string;
  hypothesis: Hypothesis;
  result: RedTeamResult;
  onAcceptCounter: (f: Omit<HypothesisFinding, "accepted_by" | "accepted_at" | "suggested_by_model">) => void;
  onInvestigateAlt: (alt: HypothesisSuggestion) => void;
  acceptAltPending: (alt: HypothesisSuggestion) => boolean;
  onDismiss: () => void;
}) {
  const empty =
    result.counter_evidence.length === 0 &&
    result.alternatives.length === 0 &&
    result.bias_flags.length === 0 &&
    result.logical_gaps.length === 0;

  return (
    <section className="mt-3 border border-amber-300 bg-amber-50/40 rounded p-3">
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <h5 className="text-[12px] font-semibold text-amber-900">Red-team challenge</h5>
          <p className="text-[11px] text-amber-800/80">
            Critic agent: attacked this hypothesis, did not look for supporting evidence.
            {result.model ? <> · <span className="font-mono">{result.model}</span></> : null}
          </p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="text-[11px] text-slate-600 hover:underline"
        >
          Close
        </button>
      </div>

      {empty ? (
        <div className="text-[11px] text-slate-600 italic">
          Red-team found no counter-evidence, alternatives, biases, or gaps to flag.
          Hypothesis withstood this challenge.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-red-800 font-semibold mb-1">
              Counter-evidence ({result.counter_evidence.length})
            </div>
            {result.counter_evidence.length === 0 ? (
              <div className="text-[11px] text-slate-500 italic">(none)</div>
            ) : (
              <ul className="space-y-1.5">
                {result.counter_evidence.map((c, i) => (
                  <li key={i} className="bg-white border border-red-200 rounded p-2">
                    <div className="text-[11px] text-slate-800 pl-2 border-l-2 border-red-300">
                      "{c.excerpt}"
                    </div>
                    {c.rationale ? (
                      <div className="text-[11px] text-slate-600 italic mt-0.5">{c.rationale}</div>
                    ) : null}
                    {c.source_doc_filename ? (
                      <div className="text-[10px] text-slate-400 font-mono mt-0.5">{c.source_doc_filename}</div>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => onAcceptCounter(c)}
                      className="mt-1 px-2 py-0.5 text-[11px] rounded bg-red-700 text-white hover:bg-red-800"
                    >
                      Add to record
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wide text-purple-800 font-semibold mb-1">
              Alternatives ({result.alternatives.length})
            </div>
            {result.alternatives.length === 0 ? (
              <div className="text-[11px] text-slate-500 italic">(none)</div>
            ) : (
              <ul className="space-y-1.5">
                {result.alternatives.map((a, i) => {
                  const pending = acceptAltPending(a);
                  return (
                    <li key={i} className="bg-white border border-purple-200 rounded p-2">
                      <div className="text-[12px] font-semibold text-slate-900">{a.title}</div>
                      {a.body ? <div className="text-[11px] text-slate-700 mt-0.5">{a.body}</div> : null}
                      {a.rationale ? (
                        <div className="text-[11px] text-purple-700 italic mt-0.5">{a.rationale}</div>
                      ) : null}
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() => onInvestigateAlt(a)}
                        className="mt-1 px-2 py-0.5 text-[11px] rounded bg-purple-700 text-white hover:bg-purple-800 disabled:opacity-50"
                      >
                        {pending ? "Saving…" : "Investigate this instead"}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wide text-amber-800 font-semibold mb-1">
              Biases + gaps
            </div>
            {result.bias_flags.length > 0 ? (
              <div className="mb-2">
                <div className="text-[10px] uppercase tracking-wide text-amber-700">Bias flags</div>
                <BiasFlagChips slugs={result.bias_flags} />
                <div className="text-[10px] text-slate-500 italic mt-0.5">
                  (now persisted on the hypothesis)
                </div>
              </div>
            ) : null}
            {result.logical_gaps.length > 0 ? (
              <div>
                <div className="text-[10px] uppercase tracking-wide text-amber-700">Logical gaps</div>
                <ul className="text-[11px] text-slate-700 space-y-0.5 mt-0.5">
                  {result.logical_gaps.map((g, i) => <li key={i}>· {g}</li>)}
                </ul>
              </div>
            ) : null}
            {result.bias_flags.length === 0 && result.logical_gaps.length === 0 ? (
              <div className="text-[11px] text-slate-500 italic">(none)</div>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}


// ── De-novo generator — no brain dump, case docs only ────────────────────

function DeNovoGenerator({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const [suggestions, setSuggestions] = useState<HypothesisSuggestion[]>([]);
  const [model, setModel] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [accepted, setAccepted] = useState<string[]>([]);

  const acceptMut = useMutation({
    mutationFn: (s: HypothesisSuggestion) => createHypothesis(caseId, {
      title: s.title,
      body: s.body,
      rationale: s.rationale,
      origin: "ai_de_novo",
      model,
    }),
    onSuccess: (_h, s) => {
      qc.invalidateQueries({ queryKey: ["case-hypotheses", caseId] });
      setAccepted((p) => p.includes(s.title) ? p : [...p, s.title]);
    },
  });

  const run = async () => {
    setError("");
    setRunning(true);
    setSuggestions([]);
    try {
      const resp = await generateDeNovoHypotheses(caseId);
      setSuggestions(resp.suggestions);
      setModel(resp.model ?? "");
      setAccepted([]);
      setDismissed(new Set());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const visible = suggestions.filter((s) => !dismissed.has(s.title) && !accepted.includes(s.title));

  return (
    <section className="border border-teal-200 bg-teal-50/30 rounded p-4">
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div>
          <h3 className="text-[13px] font-semibold text-slate-900">De-novo — no brain dump</h3>
          <p className="text-[11px] text-slate-500">
            Fresh-eyes agent. Reads the case documents <em>without</em> your framing
            and proposes hypotheses the documents raise but no one has answered.
            Use when you're stuck or suspicious of your own theory.
          </p>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={running}
          className="px-3 py-1.5 text-xs rounded bg-teal-700 text-white hover:bg-teal-800 disabled:opacity-50 shrink-0"
        >
          {running ? "Reading…" : suggestions.length > 0 ? "Refresh" : "Generate from case docs"}
        </button>
      </div>

      {accepted.length > 0 ? (
        <div className="text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-2 py-1 mb-2">
          ✓ {accepted.length} de-novo hypothesis{accepted.length === 1 ? "" : "es"} under investigation — see list below.
        </div>
      ) : null}

      {error ? <div className="text-xs text-red-700">{error}</div> : null}
      {running ? <div className="text-xs text-slate-500 italic">Reading the documents…</div> : null}

      {visible.length > 0 ? (
        <ul className="space-y-2 mt-2">
          {visible.map((s) => {
            const isPending = acceptMut.isPending && acceptMut.variables?.title === s.title;
            return (
              <li key={s.title} className="bg-white border border-slate-200 rounded p-2.5">
                <div className="flex items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-slate-900">{s.title}</div>
                    {s.body ? <div className="text-xs text-slate-700 mt-0.5 leading-snug">{s.body}</div> : null}
                    {s.rationale ? (
                      <div className="text-[11px] text-teal-700 italic mt-1">{s.rationale}</div>
                    ) : null}
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    <button
                      type="button"
                      disabled={isPending}
                      onClick={() => acceptMut.mutate(s)}
                      className="px-2 py-0.5 text-[11px] rounded bg-teal-700 text-white hover:bg-teal-800 disabled:opacity-50"
                    >
                      {isPending ? "Saving…" : "Investigate"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setDismissed((p) => new Set(p).add(s.title))}
                      className="px-2 py-0.5 text-[11px] rounded border border-slate-200 text-slate-600 hover:bg-slate-100"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}


// ── Bias flag chips — closed vocab fetched from /hypothesis-bias-vocab ──

function BiasFlagChips({ slugs }: { slugs: string[] }) {
  const { data } = useQuery({
    queryKey: ["bias-vocab"],
    queryFn: getBiasVocab,
    staleTime: 60 * 60_000,
  });
  const lookup = useMemo(() => {
    const m = new Map<string, BiasFlagDef>();
    for (const f of data?.flags ?? []) m.set(f.slug, f);
    return m;
  }, [data]);

  if (slugs.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-1.5">
      {slugs.map((slug) => {
        const def = lookup.get(slug);
        return (
          <span
            key={slug}
            title={def?.tooltip ?? slug}
            className="inline-flex items-center px-1.5 py-0.5 rounded-full border text-[10px] bg-amber-50 text-amber-900 border-amber-300"
          >
            ⚠ {def?.label ?? slug}
          </span>
        );
      })}
    </div>
  );
}


function FindingRow({ finding: f }: { finding: HypothesisFinding }) {
  return (
    <div className="flex items-start gap-2">
      <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full border text-[10px] capitalize shrink-0 ${FINDING_CHIP_CLS[f.kind as HypothesisFindingKind]}`}>
        {f.kind}
      </span>
      <div className="flex-1 min-w-0">
        {f.excerpt ? (
          <div className="text-[11px] text-slate-800 pl-2 border-l-2 border-slate-200">"{f.excerpt}"</div>
        ) : null}
        {f.rationale ? (
          <div className="text-[10px] text-slate-500 italic mt-0.5">{f.rationale}</div>
        ) : null}
        {f.source_doc_filename ? (
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">{f.source_doc_filename}</div>
        ) : null}
      </div>
    </div>
  );
}
