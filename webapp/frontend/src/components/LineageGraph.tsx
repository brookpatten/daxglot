/**
 * LineageGraph — Cytoscape.js DAG visualisation of measure lineage.
 *
 * Renders tables as compound (parent) nodes that enclose their columns.
 * In compare mode each measure's edges are drawn with a distinct colour;
 * shared edges fan out with per-measure bezier offsets so both colours show.
 */

import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
// @ts-ignore — cytoscape-dagre has no bundled types
import dagre from "cytoscape-dagre";
import type { GraphMeasure, CyElement } from "../utils/lineageGraph";
import { buildLineageElements } from "../utils/lineageGraph";
import type { WindowSpec } from "../types/measure";
import styles from "./LineageGraph.module.css";

// Register the dagre layout once
try {
    cytoscape.use(dagre);
} catch {
    // already registered — safe to ignore
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// Stylesheet — node colors come from data(bgColor/borderColor/nodeTextColor)
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildCyStyle(): any[] {
    return [
        // ---- table compound container ----
        {
            selector: "node[type='table']",
            style: {
                "background-color": "data(bgColor)",
                "border-color": "data(borderColor)",
                "border-width": 2,
                "label": "data(label)",
                "text-valign": "top",
                "text-halign": "center",
                "font-size": 10,
                "font-weight": "bold",
                "color": "data(nodeTextColor)",
                "text-wrap": "wrap",
                "text-max-width": "140px",
                "padding": "16px",
                "shape": "roundrectangle",
            },
        },
        // ---- column nodes (ellipse) ----
        {
            selector: "node[type='column']",
            style: {
                "background-color": "data(bgColor)",
                "border-color": "data(borderColor)",
                "border-width": 1.5,
                "label": "data(label)",
                "text-valign": "center",
                "text-halign": "center",
                "font-size": 9,
                "color": "data(nodeTextColor)",
                "text-wrap": "wrap",
                "text-max-width": "90px",
                "shape": "ellipse",
                "width": "label",
                "height": 32,
                "padding": "6px",
            },
        },
        // ---- metric-view compound (dashed border) ----
        {
            selector: "node[type='metric_view']",
            style: {
                "background-color": "data(bgColor)",
                "border-color": "data(borderColor)",
                "border-width": 2,
                "border-style": "dashed",
                "label": "data(label)",
                "text-valign": "top",
                "text-halign": "center",
                "font-size": 10,
                "font-weight": "bold",
                "color": "data(nodeTextColor)",
                "text-wrap": "wrap",
                "text-max-width": "140px",
                "padding": "16px",
                "shape": "roundrectangle",
            },
        },
        // ---- measure node (hexagon) ----
        {
            selector: "node[type='measure']",
            style: {
                "background-color": "data(bgColor)",
                "border-color": "data(borderColor)",
                "border-width": 2.5,
                "label": "data(label)",
                "text-valign": "center",
                "text-halign": "center",
                "font-size": 10,
                "font-weight": "bold",
                "color": "data(nodeTextColor)",
                "text-wrap": "wrap",
                "text-max-width": "110px",
                "shape": "hexagon",
                "width": "label",
                "height": 46,
                "padding": "8px",
            },
        },
        // ---- edges — colour resolved from data ----
        {
            selector: "edge",
            style: {
                "line-color": "data(color)",
                "target-arrow-color": "data(color)",
                "target-arrow-shape": "triangle",
                "arrow-scale": 1.1,
                "curve-style": "bezier",
                "width": 1.8,
                "opacity": 0.85,
            },
        },
        // ---- hover ----
        {
            selector: "node:active, edge:active",
            style: { "overlay-opacity": 0.12 },
        },
    ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
    measures: GraphMeasure[];
    /** One hex/rgb colour per measure; defaults to PILL_COLORS */
    measureColors?: string[];
    /** Pixel height of the graph container */
    height?: number;
}

export const PILL_COLORS = [
    "#6f42c1", "#0d6efd", "#198754", "#dc3545", "#fd7e14", "#0dcaf0",
];

function windowSummary(w: WindowSpec[]): string {
    if (w.length === 0) return "";
    return w.map((s) => [s.order, s.range, s.semiadditive].filter(Boolean).join(" · ")).join("; ");
}

export function LineageGraph({ measures, measureColors, height = 340 }: Props) {
    const colors = measureColors ?? PILL_COLORS.slice(0, measures.length);
    const containerRef = useRef<HTMLDivElement>(null);
    const cyRef = useRef<cytoscape.Core | null>(null);

    // Stable JSON key — re-runs only when element data changes
    const elementsKey = JSON.stringify(
        measures.map((m) => ({ id: m.id, lineage: m.lineage, window: m.window }))
    );

    useEffect(() => {
        if (!containerRef.current) return;

        const elements: CyElement[] = buildLineageElements(measures, colors);

        if (elements.length === 0) return;

        const cy = cytoscape({
            container: containerRef.current,
            elements: elements as cytoscape.ElementDefinition[],
            style: buildCyStyle(),
            layout: {
                name: "dagre",
                rankDir: "LR",        // left → right flow
                nodeSep: 24,
                rankSep: 60,
                padding: 20,
                fit: true,
            } as cytoscape.LayoutOptions,
            userZoomingEnabled: true,
            userPanningEnabled: true,
            minZoom: 0.2,
            maxZoom: 3,
            wheelSensitivity: 0.3,
        });

        // Tooltip on hover — show full table.column + type
        cy.on("mouseover", "node[type='column']", (evt) => {
            const node = evt.target;
            const tip = document.createElement("div");
            tip.id = "cy-tooltip";
            tip.className = styles.tooltip;
            tip.textContent = `${node.data("parent")?.replace("table:", "") ?? ""}`.replace("table:", "") +
                `.${node.data("label")} [${node.data("col_type") ?? "?"}]`;
            document.body.appendChild(tip);
        });
        cy.on("mousemove", (evt) => {
            const tip = document.getElementById("cy-tooltip");
            if (tip) { tip.style.left = `${evt.originalEvent.pageX + 12}px`; tip.style.top = `${evt.originalEvent.pageY + 12}px`; }
        });
        cy.on("mouseout", "node[type='column']", () => {
            document.getElementById("cy-tooltip")?.remove();
        });

        // Tooltip on measure node — show full expr + window
        cy.on("mouseover", "node[type='measure']", (evt) => {
            const node = evt.target;
            const tip = document.createElement("div");
            tip.id = "cy-tooltip";
            tip.className = styles.tooltip;
            const windowStr: string = node.data("windowSummary") ?? "";
            tip.textContent = [node.data("expr") ?? "", windowStr].filter(Boolean).join("  |  ");
            document.body.appendChild(tip);
        });
        cy.on("mouseout", "node[type='measure']", () => {
            document.getElementById("cy-tooltip")?.remove();
        });

        cyRef.current = cy;

        // Apply split-gradient background to shared nodes (owned by 2+ measures)
        cy.nodes("[?isShared]").forEach((node) => {
            const gc1: string = node.data("gc1") ?? "";
            const gc2: string = node.data("gc2") ?? "";
            if (gc1 && gc2) {
                node.style("background-fill", "linear-gradient");
                node.style("background-gradient-stop-colors", `${gc1} ${gc2}`);
                node.style("background-gradient-stop-positions", "0 100");
                node.style("background-gradient-direction", "to-right");
            }
        });

        // Apply per-edge bezier offsets so parallel (shared) edges are visible
        cy.edges().forEach((edge) => {
            const offset: number = edge.data("curveOffset") ?? 0;
            if (offset !== 0) {
                edge.style("curve-style", "unbundled-bezier");
                edge.style("control-point-distances", offset);
                edge.style("control-point-weights", 0.5);
            }
        });

        return () => {
            document.getElementById("cy-tooltip")?.remove();
            cy.destroy();
            cyRef.current = null;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [elementsKey]);

    const hasLineage = measures.some((m) => m.lineage.length > 0);

    if (!hasLineage) {
        return (
            <div className={styles.empty}>
                No lineage data available. Re-collect with lineage enabled.
            </div>
        );
    }

    return (
        <div className={styles.wrapper}>
            {/* Legend */}
            <div className={styles.legend}>
                {/* Entity shape guide */}
                <span className={styles.legendItem}>
                    <span className={styles.legendSwatchSquare} />
                    Table
                </span>
                <span className={styles.legendItem}>
                    <span className={styles.legendSwatchEllipse} />
                    Column
                </span>
                <span className={styles.legendItem}>
                    <span className={`${styles.legendSwatchSquare} ${styles.legendSwatchDashed}`} />
                    Metric View
                </span>
                <span className={styles.legendItem}>
                    <span className={styles.legendSwatchHex} />
                    Measure
                </span>
                {/* Separator */}
                {measures.length > 1 && (
                    <span className={styles.legendSep} />
                )}
                {/* Measure colour lines */}
                {measures.map((m, i) => (
                    <span key={m.id} className={styles.legendItem}>
                        <span className={styles.legendEdge} style={{ background: colors[i % colors.length] }} />
                        {m.name}
                    </span>
                ))}
                {/* Shared indicator */}
                {measures.length > 1 && (
                    <span className={styles.legendItem}>
                        <span
                            className={styles.legendSwatchSquare}
                            style={{
                                background: `linear-gradient(to right, ${colors[0]}, ${colors[1 % colors.length]})`,
                                opacity: 0.45,
                                borderColor: "#6c757d",
                            }}
                        />
                        Shared
                    </span>
                )}
            </div>

            {/* Cytoscape canvas */}
            <div
                ref={containerRef}
                className={styles.canvas}
                style={{ height }}
            />

            {/* Measure details strip — expression + window specs */}
            <div className={styles.measureDetails}>
                {measures.map((m, i) => {
                    const color = colors[i % colors.length];
                    const ws = windowSummary(m.window);
                    return (
                        <div key={m.id} className={styles.measureDetail}>
                            <span className={styles.measureDetailPill} style={{ background: color }} />
                            <div className={styles.measureDetailBody}>
                                <div className={styles.measureDetailHeader}>
                                    <span className={styles.measureDetailName} style={{ color }}>{m.name}</span>
                                    <span className={styles.measureDetailView}>{m.metric_view}</span>
                                </div>
                                <code className={styles.measureDetailExpr}>{m.expr}</code>
                                {ws && (
                                    <div className={styles.measureDetailWindow}>
                                        <span className={styles.measureDetailWindowLabel}>Window</span>
                                        {m.window.map((w, wi) => (
                                            <span key={wi} className={styles.measureDetailWindowSpec}>
                                                <strong>{w.order}</strong>
                                                <span>{w.range}</span>
                                                {w.semiadditive && <em>{w.semiadditive}</em>}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
