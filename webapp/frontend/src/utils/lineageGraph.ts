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

import type { DimensionDefinition, LineageColumn, WindowSpec } from "../types/measure";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface GraphMeasure {
    id: string;
    name: string;
    expr: string;
    metric_view: string;
    source_table: string;
    dimensions: DimensionDefinition[];
    lineage: LineageColumn[];
    window: WindowSpec[];
}

export interface CyNodeData {
    id: string;
    label: string;
    /** Visual category */
    type: "catalog" | "schema" | "table" | "column" | "dimension" | "measure" | "metric_view";
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

/** Parse a fully-qualified name (catalog.schema.local) into its parts. */
function parseFQN(name: string): { catalog: string | null; schema: string | null; local: string } {
    const parts = name.split(".");
    if (parts.length >= 3) return { catalog: parts[0], schema: parts[1], local: parts.slice(2).join(".") };
    if (parts.length === 2) return { catalog: null, schema: parts[0], local: parts[1] };
    return { catalog: null, schema: null, local: name };
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

/** Unique dimension node id */
function dimNodeId(metric_view: string, dim_name: string) {
    return `dim:${metric_view}.${dim_name}`;
}

/**
 * Ensure catalog and schema container nodes exist in nodeMap.
 * Returns their node ids (null if no catalog/schema present in the FQN).
 */
function ensureCatalogSchema(
    catalog: string | null,
    schema: string | null,
    measureIdx: number,
    nodeMap: Map<string, CyNodeData>
): { catNodeId: string | null; schNodeId: string | null } {
    let catNodeId: string | null = null;
    let schNodeId: string | null = null;

    if (catalog) {
        catNodeId = `cat:${catalog}`;
        if (!nodeMap.has(catNodeId)) {
            nodeMap.set(catNodeId, { id: catNodeId, label: catalog + "\n(catalog)", type: "catalog", measures: [] });
        }
        const catNode = nodeMap.get(catNodeId)!;
        if (!catNode.measures!.includes(measureIdx)) catNode.measures!.push(measureIdx);
    }

    if (schema) {
        schNodeId = catalog ? `schema:${catalog}.${schema}` : `schema:${schema}`;
        if (!nodeMap.has(schNodeId)) {
            nodeMap.set(schNodeId, {
                id: schNodeId,
                label: schema + "\n(schema)",
                type: "schema",
                parent: catNodeId ?? undefined,
                measures: [],
            });
        }
        const schNode = nodeMap.get(schNodeId)!;
        if (!schNode.measures!.includes(measureIdx)) schNode.measures!.push(measureIdx);
    }

    return { catNodeId, schNodeId };
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
    const { catalog, schema, local: localName } = parseFQN(col.table);
    const { schNodeId } = ensureCatalogSchema(catalog, schema, measureIdx, nodeMap);

    const tId = tableId(col.table);
    const cId = colId(col.table, col.column);

    // Table/view container node (nested inside its schema)
    if (!nodeMap.has(tId)) {
        const typeLabel = col.type === "VIEW" ? "(view)" : "(table)";
        nodeMap.set(tId, {
            id: tId,
            label: localName + "\n" + typeLabel,
            type: "table",
            parent: schNodeId ?? undefined,
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

        // Metric-view compound node (nested inside its schema)
        const mvParts = parseFQN(m.metric_view);
        const { schNodeId: mvSchNodeId } = ensureCatalogSchema(mvParts.catalog, mvParts.schema, mi, nodeMap);
        const mvNodeId = mvId(m.metric_view);
        if (!nodeMap.has(mvNodeId)) {
            nodeMap.set(mvNodeId, {
                id: mvNodeId,
                label: mvParts.local + "\n(metric view)",
                type: "metric_view",
                parent: mvSchNodeId ?? undefined,
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
                label: m.expr + "\n(measure)",
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

        // ---------------------------------------------------------------------------
        // Dimension nodes — one per dimension referenced in window specs
        // ---------------------------------------------------------------------------
        const usedDimNames = new Set(m.window.map((w) => w.order).filter(Boolean));
        for (const dimName of usedDimNames) {
            const dim = m.dimensions.find((d) => d.name === dimName);
            if (!dim) continue;

            const dId = dimNodeId(m.metric_view, dim.name);
            if (!nodeMap.has(dId)) {
                nodeMap.set(dId, {
                    id: dId,
                    label: dim.name + "\n(dimension)",
                    type: "dimension",
                    parent: mvNodeId,
                    measures: [],
                });
            }
            const dNode = nodeMap.get(dId)!;
            if (!dNode.measures!.includes(mi)) dNode.measures!.push(mi);

            // Edge: dimension → measure
            const dimMeasureKey = `${dId}--${mNodeId}`;
            if (!edgeMeasures.has(dimMeasureKey)) edgeMeasures.set(dimMeasureKey, new Set());
            edgeMeasures.get(dimMeasureKey)!.add(mi);

            // Source column node in the source_table (may be synthetic)
            if (m.source_table) {
                const stParts = parseFQN(m.source_table);
                const { schNodeId: stSchNodeId } = ensureCatalogSchema(stParts.catalog, stParts.schema, mi, nodeMap);
                const stId = tableId(m.source_table);
                const scId = colId(m.source_table, dim.expr);

                if (!nodeMap.has(stId)) {
                    nodeMap.set(stId, {
                        id: stId,
                        label: stParts.local + "\n(table)",
                        type: "table",
                        parent: stSchNodeId ?? undefined,
                        measures: [],
                    });
                }
                const stNode = nodeMap.get(stId)!;
                if (!stNode.measures!.includes(mi)) stNode.measures!.push(mi);

                if (!nodeMap.has(scId)) {
                    nodeMap.set(scId, {
                        id: scId,
                        label: dim.expr + "\n(key)",
                        type: "column",
                        parent: stId,
                        col_type: "DIMENSION",
                        measures: [],
                    });
                }
                const scNode = nodeMap.get(scId)!;
                if (!scNode.measures!.includes(mi)) scNode.measures!.push(mi);

                // Edge: source column → dimension
                const colDimKey = `${scId}--${dId}`;
                if (!edgeMeasures.has(colDimKey)) edgeMeasures.set(colDimKey, new Set());
                edgeMeasures.get(colDimKey)!.add(mi);
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Post-process: assign per-node colours derived from measure ownership
    // ---------------------------------------------------------------------------
    for (const node of nodeMap.values()) {
        // Catalog/schema containers: no background fill, neutral border
        if (node.type === "catalog" || node.type === "schema") {
            node.bgColor = "transparent";
            node.borderColor = "#adb5bd";
            node.nodeTextColor = "#6c757d";
            node.isShared = false;
            continue;
        }

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
