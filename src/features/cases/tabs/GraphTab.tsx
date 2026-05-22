// Node-link visualization of the case's graph neighborhood.
//
// Reads from /graph/cases/{id}/neighborhood (the new GraphService spine).
// Confidence slider filters weak edges; depth slider widens the view.
// Color coding by node kind; edge width scales with confidence.
//
// Layout: simple polar arrangement — the case in the center, neighbors
// grouped in concentric rings by kind. Avoids the dependency + complexity
// of a real force-directed simulation while keeping the picture readable
// for the typical 10-30 node case neighborhoods.

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
  case: "#1e40af",         // blue-800 — the focal case
  person: "#7c2d12",       // orange-900
  document: "#065f46",     // emerald-800
  hypothesis: "#6b21a8",   // purple-800
  tag: "#475569",          // slate-600
  timeline_event: "#9a3412",
  passage: "#52525b",
};
const NODE_TEXT_LIGHT = "#ffffff";

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
  const [depth, setDepth] = useState(2);
  const [minConfidence, setMinConfidence] = useState(0.4);
  const [includeWeak, setIncludeWeak] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["case-neighborhood", caseId, depth, minConfidence],
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
              Case neighborhood — persons, documents, hypotheses, tags. Drag to
              pan, scroll to zoom. Confidence + depth controls filter the view.
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
        )}
      </div>
    </div>
  );
}


function onNodeClick(node: Node) {
  // Cases → open the case workspace. Other kinds → no-op (could open a
  // detail drawer in a follow-up).
  const kind = (node.data as { kind?: string } | undefined)?.kind;
  const rawId = (node.data as { rawId?: string } | undefined)?.rawId;
  if (kind === "case" && rawId) {
    setHashPath(`${ROUTES.casePrefix}${rawId}`);
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
  // categories read at a glance.
  const radiusByKind: Record<string, number> = {
    person: 180,
    document: 280,
    hypothesis: 360,
    tag: 440,
    timeline_event: 520,
    passage: 600,
    case: 200, // other cases (not focal) — close-ish
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

  // Focal node — centered.
  if (focal) {
    nodes.push({
      id: focal.id,
      type: "default",
      position: { x: 0, y: 0 },
      data: {
        label: shortLabel(focal),
        kind: focal.kind,
        rawId: rawIdFromGraphId(focal.id),
      },
      style: nodeStyle(focal.kind, true),
    });
  }

  // Ring nodes.
  for (const [kind, list] of buckets.entries()) {
    const radius = radiusByKind[kind] ?? 300;
    const baseAngle = startAngleByKind[kind] ?? 0;
    const sweep = Math.min(Math.PI * 1.6, Math.max(Math.PI / 2, list.length * 0.35));
    const step = sweep / Math.max(1, list.length - 1);
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
        style: nodeStyle(n.kind, false),
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


function nodeStyle(kind: string, isFocal: boolean): React.CSSProperties {
  const fill = NODE_FILL[kind] ?? "#475569";
  return {
    background: fill,
    color: NODE_TEXT_LIGHT,
    border: isFocal ? "3px solid #fbbf24" : "1px solid rgba(0,0,0,0.2)",
    borderRadius: 8,
    padding: 6,
    fontSize: 11,
    fontWeight: isFocal ? 600 : 500,
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
