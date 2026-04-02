/**
 * Utilities for building Cytoscape.js element arrays from measure lineage data.
 *
 * Graph structure (left-to-right):
 *   [source tables] → [intermediate tables/views] → [metric view] → [measure]
 *
 * Tables are rendered as compound (parent) nodes that group their columns.
 * In compare mode each edge is drawn once per measure that uses it, with a
 * slight bezier curve offset so both colours are visible when shared.
 */

import type { LineageColumn, WindowSpec } from "../types/measure";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface GraphMeasure {
    id: string;
    name: string;
    expr: string;
    metric_view: string;
    lineage: LineageColumn[];
    window: WindowSpec[];
}

export interface CyNodeData {
    id: string;
    label: string;
    /** Visual category */
    type: "table" | "column" | "measure" | "metric_view";
    parent?: string;
    /** Full expression (measure nodes only) */
    expr?: string;
    /** Pre-formatted window summary string (measure nodes only) */
    windowSummary?: string;
    /** Metric-view name shown on measure node */
    metric_view?: string;
    /** Column type string (TABLE, VIEW, UNKNOWN …) */
    col_type?: string;
    /** Indices of measures that reference this node */
    measures?: number[];
    /** Computed background fill color (rgba string) */
    bgColor?: string;
    /** Computed border color */
    borderColor?: string;
    /** Computed label text color */
    nodeTextColor?: string;
    /** True when owned by 2+ measures */
    isShared?: boolean;
    /** Pre-computed rgba gradient colors for shared nodes [gc1, gc2] */
    gc1?: string;
    gc2?: string;
}

export interface CyEdgeData {
    id: string;
    source: string;
    target: string;
    /** Which measure owns this edge (0-based index into the measures array) */
    measureIdx: number;
    /** Colour resolved from measureIdx */
    color: string;
    /**
     * Bezier control-point offset in pixels.  For shared edges we emit one
     * edge element per measure and spread them so both colours show.
     */
    curveOffset: number;
}

export type CyElement =
    | { group: "nodes"; data: CyNodeData }
    | { group: "edges"; data: CyEdgeData };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Hex color → rgba string with given alpha for tinted node backgrounds */
export function hexToRgba(hex: string, alpha: number): string {
    const h = hex.replace("#", "");
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    return `rgba(${r},${g},${b},${alpha})`;
}

/** Shorten qualified names: keep last two dot-segments (schema.table) */
function shortName(full: string): string {
    const parts = full.split(".");
    return parts.slice(-2).join(".");
}

/** Unique table node id */
function tableId(table: string) {
    return `table:${table}`;
}

/** Unique column node id */
function colId(table: string, column: string) {
    return `col:${table}.${column}`;
}

/** Unique measure node id */
function measureNodeId(id: string) {
    return `measure:${id}`;
}

/** Unique metric-view node id (used as a compound parent for the measure) */
function mvId(metric_view: string) {
    return `mv:${metric_view}`;
}

// ---------------------------------------------------------------------------
// Core recursive walker
// ---------------------------------------------------------------------------

/**
 * Walk one LineageColumn node and all its upstream ancestors, adding
 * node / edge records to the accumulator maps.
 *
 * @param col          Current lineage node
 * @param childId      The id of the node this column flows **into**
 * @param measureIdx   Index into the measures array (for edge colouring)
 * @param nodeMap      Accumulator: id → CyNodeData (deduped by id)
 * @param edgeMeasures Accumulator: edgeKey → Set<measureIdx>
 */
function walkLineage(
    col: LineageColumn,
    childId: string,
    measureIdx: number,
    nodeMap: Map<string, CyNodeData>,
    edgeMeasures: Map<string, Set<number>>
): void {
    const tId = tableId(col.table);
    const cId = colId(col.table, col.column);

    // Table parent node
    if (!nodeMap.has(tId)) {
        nodeMap.set(tId, {
            id: tId,
            label: shortName(col.table) + "\n(table)",
            type: "table",
            measures: [],
        });
    }
    // Track which measures reference this table
    const tNode = nodeMap.get(tId)!;
    if (!tNode.measures!.includes(measureIdx)) tNode.measures!.push(measureIdx);

    // Column node (child of its table)
    if (!nodeMap.has(cId)) {
        nodeMap.set(cId, {
            id: cId,
            label: col.column + "\n" + col.type.toLowerCase(),
            type: "column",
            parent: tId,
            col_type: col.type,
            measures: [],
        });
    }
    const cNode = nodeMap.get(cId)!;
    if (!cNode.measures!.includes(measureIdx)) cNode.measures!.push(measureIdx);

    // Edge from this column → its consumer (child node)
    const edgeKey = `${cId}--${childId}`;
    if (!edgeMeasures.has(edgeKey)) edgeMeasures.set(edgeKey, new Set());
    edgeMeasures.get(edgeKey)!.add(measureIdx);

    // Recurse into upstream ancestors
    for (const up of col.upstream) {
        walkLineage(up, cId, measureIdx, nodeMap, edgeMeasures);
    }
}

// ---------------------------------------------------------------------------
// Public builder
// ---------------------------------------------------------------------------

/**
 * Build a complete Cytoscape element array for one or more measures.
 *
 * - Single measure → all edges use `colors[0]`.
 * - Multiple measures → each edge is drawn once per measure that uses it,
 *   with bezier curve offsets so parallel edges are visible.
 * - Columns from the same source table are grouped inside a compound node.
 */
export function buildLineageElements(
    measures: GraphMeasure[],
    colors: string[]
): CyElement[] {
    // Primary registers
    const nodeMap = new Map<string, CyNodeData>();
    // edgeKey (source--target) → Set<measureIdx>
    const edgeMeasures = new Map<string, Set<number>>();

    for (let mi = 0; mi < measures.length; mi++) {
        const m = measures[mi];

        // Metric-view compound node (parent for the measure)
        const mvNodeId = mvId(m.metric_view);
        if (!nodeMap.has(mvNodeId)) {
            nodeMap.set(mvNodeId, {
                id: mvNodeId,
                label: shortName(m.metric_view) + "\n(metric view)",
                type: "metric_view",
                measures: [],
            });
        }
        const mvNode = nodeMap.get(mvNodeId)!;
        if (!mvNode.measures!.includes(mi)) mvNode.measures!.push(mi);

        // Measure node
        const mNodeId = measureNodeId(m.id);
        if (!nodeMap.has(mNodeId)) {
            const wSummary = m.window.length > 0
                ? m.window.map((s) => [s.order, s.range, s.semiadditive].filter(Boolean).join(" · ")).join("; ")
                : undefined;
            nodeMap.set(mNodeId, {
                id: mNodeId,
                label: m.name + "\n(measure)",
                type: "measure",
                parent: mvNodeId,
                expr: m.expr,
                windowSummary: wSummary,
                metric_view: m.metric_view,
                measures: [mi],
            });
        } else {
            // Duplicate measure ids (shouldn't happen) — just add measureIdx
            const existing = nodeMap.get(mNodeId)!;
            if (!existing.measures!.includes(mi)) existing.measures!.push(mi);
        }

        // Walk lineage tree
        for (const col of m.lineage) {
            walkLineage(col, mNodeId, mi, nodeMap, edgeMeasures);
        }
    }

    // ---------------------------------------------------------------------------
    // Post-process: assign per-node colours derived from measure ownership
    // ---------------------------------------------------------------------------
    for (const node of nodeMap.values()) {
        const mIdxs = node.measures ?? [];
        const isCompound = node.type === "table" || node.type === "metric_view";
        const alpha = isCompound ? 0.07 : 0.15;

        if (mIdxs.length === 0) {
            node.bgColor = "#f8f9fa";
            node.borderColor = "#adb5bd";
            node.nodeTextColor = "#495057";
            node.isShared = false;
        } else if (mIdxs.length === 1) {
            const c = colors[mIdxs[0] % colors.length];
            node.bgColor = hexToRgba(c, alpha);
            node.borderColor = c;
            node.nodeTextColor = "#1a1a2e";
            node.isShared = false;
        } else {
            const c1 = colors[mIdxs[0] % colors.length];
            const c2 = colors[mIdxs[1] % colors.length];
            node.bgColor = hexToRgba(c1, alpha);  // fallback solid
            node.borderColor = "#6c757d";
            node.nodeTextColor = "#212529";
            node.isShared = true;
            node.gc1 = hexToRgba(c1, alpha + 0.05);
            node.gc2 = hexToRgba(c2, alpha + 0.05);
        }
    }

    // ---------------------------------------------------------------------------
    // Materialise elements array
    // ---------------------------------------------------------------------------
    const elements: CyElement[] = [];

    // Nodes
    for (const data of nodeMap.values()) {
        elements.push({ group: "nodes", data });
    }

    // Edges — emit one per (edge, measure) with spread offsets
    for (const [edgeKey, measureSet] of edgeMeasures.entries()) {
        const [source, target] = edgeKey.split("--");
        const mList = Array.from(measureSet).sort();
        const count = mList.length;

        // Spacing: 0 for single edges, ±SPREAD for shared edges
        const SPREAD = 18;
        const step = count > 1 ? (2 * SPREAD) / (count - 1) : 0;

        mList.forEach((mi, pos) => {
            const offset = count > 1 ? -SPREAD + pos * step : 0;
            const color = colors[mi % colors.length];
            elements.push({
                group: "edges",
                data: {
                    id: `${edgeKey}--m${mi}`,
                    source,
                    target,
                    measureIdx: mi,
                    color,
                    curveOffset: offset,
                },
            });
        });
    }

    return elements;
}
