// Node-link visualization of the case's graph neighborhood.
//
// Reads from /graph/cases/{id}/neighborhood (the GraphService spine).
// Confidence slider filters weak edges; depth slider widens the view.
// First-time orientation: an expandable "How to read this" panel above
// the canvas explains the colors, edges, and the queries this enables.

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow, Background, Controls, MiniMap,
  type Node, type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { getCaseNeighborhood, type GraphNodeDTO, type GraphEdgeDTO } from "@/lib/api/coldcase";
import { ROUTES, setHashPath } from "@/shell/routes";


const NODE_FILL: Record<string, string> = {
  case: "#1e3a8a",         // blue-900 — other cases
  case_focal: "#f59e0b",   // amber-500 — the focal case is visually distinct
  person: "#7c2d12",       // orange-900
  document: "#065f46",     // emerald-800
  hypothesis: "#6b21a8",   // purple-800
  tag: "#475569",          // slate-600
  timeline_event: "#9a3412",
  passage: "#52525b",
};


const NODE_KIND_LABEL: Record<string, string> = {
  case: "Other case",
  person: "Person",
  document: "Document",
  hypothesis: "Hypothesis",
  tag: "Tag",
  timeline_event: "Timeline event",
  passage: "Document passage",
};


const EDGE_COLOR: Record<string, string> = {
  appears_on_case: "#1f2937",
  belongs_to_case: "#065f46",
  about_case: "#6b21a8",
  alternative_to: "#7c3aed",
  co_occurs_with: "#94a3b8",
  same_name_as: "#fcd34d",
  confirmed_same_person_as: "#10b981",
  confirmed_different_person_as: "#94a3b8",
  similar_via_tag: "#0ea5e9",
  tagged_with: "#cbd5e1",
  event_on_case: "#f59e0b",
};


export default function GraphTab({ caseId }: { caseId: string }) {
  const [depth, setDepth] = useState(1);                  // start tight to reduce visual clutter
  const [minConfidence, setMinConfidence] = useState(0.4);
  const [includeWeak, setIncludeWeak] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["case-neighborhood", caseId, depth, minConfidence, includeWeak],
    queryFn: () => getCaseNeighborhood(caseId, {
      depth, minConfidence: includeWeak ? 0 : minConfidence,
    }),
    staleTime: 30_000,
  });

  const { nodes, edges } = useMemo(() => {
    if (!data) return { nodes: [] as Node[], edges: [] as Edge[] };
    return buildLayout(caseId, data.nodes, data.edges);
  }, [data, caseId]);

  return (
    <div className="h-full flex flex-col">
      <header className="px-6 pt-4 pb-2 border-b border-slate-200">
        <div className="flex items-baseline justify-between flex-wrap gap-2">
          <div>
            <h2 className="text-[15px] font-semibold text-slate-900">Graph</h2>
            <p className="text-xs text-slate-500">
              Everything connected to this case — people, documents, hypotheses, tags.
              Drag to pan, scroll to zoom. The amber-bordered node in the centre is
              this case;{" "}
              <button
                type="button"
                onClick={() => setHelpOpen((v) => !v)}
                className="text-blue-700 hover:underline"
              >
                {helpOpen ? "hide" : "what should I use this for?"}
              </button>
            </p>
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <label className="flex items-center gap-1.5">
              <span className="text-slate-600">Depth</span>
              <input
                type="range" min={1} max={3} step={1}
                value={depth} onChange={(e) => setDepth(parseInt(e.target.value))}
                className="w-20"
              />
              <span className="font-mono text-slate-700 w-3">{depth}</span>
            </label>
            <label className="flex items-center gap-1.5">
              <span className="text-slate-600">Min confidence</span>
              <input
                type="range" min={0} max={1} step={0.05}
                value={includeWeak ? 0 : minConfidence}
                onChange={(e) => { setMinConfidence(parseFloat(e.target.value)); setIncludeWeak(false); }}
                className="w-24"
                disabled={includeWeak}
              />
              <span className="font-mono text-slate-700 w-8">
                {(includeWeak ? 0 : minConfidence).toFixed(2)}
              </span>
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="checkbox" checked={includeWeak}
                onChange={(e) => setIncludeWeak(e.target.checked)}
              />
              <span className="text-slate-600">Include speculative</span>
            </label>
          </div>
        </div>
        {data ? (
          <div className="text-[11px] text-slate-500 mt-1">
            {nodes.length} nodes · {edges.length} edges
            {data.stats ? Object.entries(data.stats).map(([k, v]) => (
              <span key={k} className="ml-2 capitalize">· {v} {k.replace("_", " ")}</span>
            )) : null}
          </div>
        ) : null}

        {helpOpen ? <HelpPanel /> : null}
      </header>

      <div className="flex-1 relative bg-slate-50">
        {isLoading ? (
          <div className="p-6 text-xs text-slate-500">Loading graph…</div>
        ) : error ? (
          <div className="p-6 text-xs text-red-700">{(error as Error).message}</div>
        ) : nodes.length === 0 ? (
          <div className="p-6 text-xs text-slate-500">
            Empty neighborhood. Add persons, documents, or hypotheses to this case.
          </div>
        ) : (
          <>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              fitView
              onNodeClick={(_, n) => onNodeClick(n)}
              nodesDraggable
              panOnDrag
              zoomOnScroll
            >
              <Background />
              <Controls />
              <MiniMap pannable zoomable />
            </ReactFlow>
            <Legend />
          </>
        )}
      </div>
    </div>
  );
}


// ── Floating legend overlay ──────────────────────────────────────────────

function Legend() {
  // Visible bottom-right; collapsible so it doesn't fight the minimap.
  const [open, setOpen] = useState(true);
  return (
    <div className="absolute top-3 right-3 max-w-xs bg-white border border-slate-300 rounded shadow-sm text-[11px] pointer-events-auto">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full px-2.5 py-1 flex items-center justify-between hover:bg-slate-50"
      >
        <span className="font-semibold text-slate-800">Legend</span>
        <span className="text-slate-500">{open ? "−" : "+"}</span>
      </button>
      {open ? (
        <div className="px-2.5 pb-2 space-y-1.5 border-t border-slate-200 pt-1.5">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Nodes</div>
          {([
            ["case_focal", "This case"],
            ["case", "Other case"],
            ["person", "Person"],
            ["document", "Document"],
            ["hypothesis", "Hypothesis"],
            ["tag", "Tag"],
            ["timeline_event", "Timeline event"],
          ] as const).map(([kind, label]) => (
            <div key={kind} className="flex items-center gap-2">
              <span className="inline-block w-4 h-3 rounded" style={{ background: NODE_FILL[kind] ?? "#475569" }} />
              <span className="text-slate-700">{label}</span>
            </div>
          ))}
          <div className="text-[10px] uppercase tracking-wide text-slate-500 mt-2">Edges</div>
          <div className="text-[10px] text-slate-600 leading-snug">
            Thickness + opacity scale with confidence (0–100%). Animated green edges
            are officer-confirmed same-person assertions. Yellow edges are weak
            name matches.
          </div>
        </div>
      ) : null}
    </div>
  );
}


// ── Help panel: what is this + why it matters + how to use ────────────────

function HelpPanel() {
  return (
    <div className="bg-blue-50/60 border border-blue-200 rounded p-3 mt-2 text-xs leading-relaxed">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-blue-900 font-semibold mb-1">
            What you're looking at
          </div>
          <p className="text-slate-700">
            A picture of <b>everything related to this case</b> — every person, document,
            hypothesis, tag, timeline event, plus any <i>other cases</i> these things touch.
            The amber-bordered node in the centre is this case. Lines connect things that
            relate.
          </p>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-blue-900 font-semibold mb-1">
            Why it's useful
          </div>
          <ul className="text-slate-700 space-y-1 list-disc list-outside ml-4">
            <li>Spot a person who shows up on two different cases at a glance</li>
            <li>See which documents support which hypotheses</li>
            <li>Catch shared evidence patterns across cases (yellow weak-match edges)</li>
            <li>Verify the file's structure before discovery — "are all the dots connected?"</li>
          </ul>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wide text-blue-900 font-semibold mb-1">
            How to use
          </div>
          <ul className="text-slate-700 space-y-1 list-disc list-outside ml-4">
            <li><b>Click a case</b> to open it</li>
            <li><b>Click a person</b> to see every case they appear on</li>
            <li><b>Drag</b> to pan; <b>scroll</b> to zoom</li>
            <li><b>Min confidence</b> slider hides weak / speculative edges. Lower it to
              surface tentative connections; raise it to see only confirmed ones.</li>
            <li><b>Depth</b> widens the view — 1 = direct connections only, 3 = neighbors-of-neighbors</li>
          </ul>
        </div>
      </div>
      <p className="text-[11px] text-slate-600 mt-3 pt-2 border-t border-blue-200">
        <b>Tip:</b> if the picture feels crowded, drop Depth to 1 and raise Min confidence
        to 0.7 — you'll see only the strongest direct connections. Then explore outward.
      </p>
    </div>
  );
}


function onNodeClick(node: Node) {
  // Cases → open the case workspace. Persons → switch to People tab where
  // the cross-case lookup lives. Other kinds → no-op for now (could open
  // a detail drawer in a follow-up).
  const kind = (node.data as { kind?: string } | undefined)?.kind;
  const rawId = (node.data as { rawId?: string } | undefined)?.rawId;
  if (kind === "case" && rawId) {
    setHashPath(`${ROUTES.casePrefix}${rawId}`);
  } else if (kind === "case_focal" && rawId) {
    // Already on this case — gentle no-op.
  }
}


// ── Layout: focal case at center, others arranged in concentric rings ──

function buildLayout(
  focalCaseId: string,
  apiNodes: GraphNodeDTO[],
  apiEdges: GraphEdgeDTO[],
): { nodes: Node[]; edges: Edge[] } {
  const focalNodeId = `case:${focalCaseId}`;

  // Bucket by kind (excluding the focal case).
  const buckets = new Map<string, GraphNodeDTO[]>();
  let focal: GraphNodeDTO | undefined;
  for (const n of apiNodes) {
    if (n.id === focalNodeId) {
      focal = n;
      continue;
    }
    const arr = buckets.get(n.kind) ?? [];
    arr.push(n);
    buckets.set(n.kind, arr);
  }

  // Concentric placement. Each kind gets its own ring radius so the
  // categories read at a glance. Wider rings so labels don't overlap.
  const radiusByKind: Record<string, number> = {
    person: 240,
    document: 380,
    hypothesis: 500,
    tag: 620,
    timeline_event: 720,
    passage: 820,
    case: 280, // other cases — close-ish but distinguishable
  };

  const startAngleByKind: Record<string, number> = {
    person: 0,
    document: Math.PI / 4,
    hypothesis: Math.PI / 2,
    tag: 3 * Math.PI / 4,
    timeline_event: Math.PI,
    case: 5 * Math.PI / 4,
    passage: 6 * Math.PI / 4,
  };

  const nodes: Node[] = [];

  // Focal node — centered. Bigger and amber so it pops.
  if (focal) {
    nodes.push({
      id: focal.id,
      type: "default",
      position: { x: 0, y: 0 },
      data: {
        label: focal.attrs?.case_number || focal.label,
        kind: "case_focal",
        rawId: rawIdFromGraphId(focal.id),
      },
      style: focalNodeStyle(),
    });
  }

  // Ring nodes.
  for (const [kind, list] of buckets.entries()) {
    const radius = radiusByKind[kind] ?? 300;
    const baseAngle = startAngleByKind[kind] ?? 0;
    // Wider sweep when many nodes so labels don't pile up.
    const sweep = Math.min(Math.PI * 1.8, Math.max(Math.PI / 2, list.length * 0.5));
    const step = list.length === 1 ? 0 : sweep / (list.length - 1);
    list.forEach((n, i) => {
      const angle = baseAngle + (list.length === 1 ? 0 : i * step - sweep / 2);
      nodes.push({
        id: n.id,
        type: "default",
        position: {
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
        },
        data: {
          label: shortLabel(n),
          kind: n.kind,
          rawId: rawIdFromGraphId(n.id),
        },
        style: nodeStyle(n.kind),
      });
    });
  }

  // Edges — width by confidence, color by kind.
  const edges: Edge[] = apiEdges.map((e, i) => {
    const color = EDGE_COLOR[e.kind] ?? "#94a3b8";
    const width = Math.max(0.5, Math.min(4, e.confidence * 3));
    const label = e.confidence < 1 ? `${(e.confidence * 100).toFixed(0)}%` : undefined;
    return {
      id: `e-${i}`,
      source: e.source,
      target: e.target,
      style: { stroke: color, strokeWidth: width, opacity: 0.5 + e.confidence * 0.5 },
      label: label,
      labelStyle: { fontSize: 9, fill: color },
      labelShowBg: false,
      animated: e.kind === "confirmed_same_person_as",
    };
  });

  return { nodes, edges };
}


function focalNodeStyle(): React.CSSProperties {
  return {
    background: NODE_FILL.case_focal,
    color: "#1f2937",
    border: "3px solid #b45309",
    borderRadius: 10,
    padding: 10,
    fontSize: 13,
    fontWeight: 700,
    width: 200,
    textAlign: "center",
    boxShadow: "0 0 0 4px rgba(245, 158, 11, 0.2)",
  };
}


function nodeStyle(kind: string): React.CSSProperties {
  const fill = NODE_FILL[kind] ?? "#475569";
  return {
    background: fill,
    color: "#ffffff",
    border: "1px solid rgba(0,0,0,0.2)",
    borderRadius: 8,
    padding: 6,
    fontSize: 11,
    fontWeight: 500,
    width: 160,
    textAlign: "center",
  };
}


function shortLabel(n: GraphNodeDTO): string {
  const label = n.label || n.id;
  if (label.length <= 32) return label;
  return label.slice(0, 29) + "…";
}


function rawIdFromGraphId(graphId: string): string {
  const idx = graphId.indexOf(":");
  return idx >= 0 ? graphId.slice(idx + 1) : graphId;
}


// `NODE_KIND_LABEL` is exported in spirit through the Legend component; the
// const is kept to document the kind → label mapping in one place.
export { NODE_KIND_LABEL };
