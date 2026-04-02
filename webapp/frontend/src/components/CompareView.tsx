import { useState } from "react";
import type { Measure } from "../types/measure";
import type { CompareResult, PairComparison } from "../types/compare";
import styles from "./CompareView.module.css";
import { LineageGraph } from "./LineageGraph";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function labelClass(label: string) {
    if (label === "Identical") return styles.labelIdentical;
    if (label === "Similar") return styles.labelSimilar;
    return styles.labelDifferent;
}

function scoreColor(score: number) {
    if (score >= 0.98) return "#065f46";
    if (score >= 0.6) return "#854d0e";
    return "#991b1b";
}

// ---------------------------------------------------------------------------
// Measure header pills
// ---------------------------------------------------------------------------

const PILL_COLORS = ["#6f42c1", "#0d6efd", "#198754", "#dc3545", "#fd7e14", "#0dcaf0"];

function MeasurePills({ measures }: { measures: Measure[] }) {
    return (
        <div
            className={styles.measuresRow}
            style={{ gridTemplateColumns: `repeat(${Math.min(measures.length, 2)}, 1fr)` }}
        >
            {measures.map((m, i) => (
                <div key={m.id} className={styles.measurePill}>
                    <span
                        className={styles.pillLabel}
                        style={{ background: PILL_COLORS[i % PILL_COLORS.length] }}
                    >
                        {String.fromCharCode(65 + i)}
                    </span>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", flexWrap: "wrap" }}>
                            <span className={styles.pillName}>{m.name}</span>
                            {m.display_name && (
                                <span style={{ fontSize: "0.8rem", color: "#6c757d", fontStyle: "italic" }}>
                                    {m.display_name}
                                </span>
                            )}
                            <span className={styles.pillView}>{m.metric_view}</span>
                        </div>
                        <code className={styles.pillExpr}>{m.expr}</code>
                    </div>
                </div>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Expression diff
// ---------------------------------------------------------------------------

function ExprBlock({ pair }: { pair: PairComparison }) {
    const [open, setOpen] = useState(!pair.expr.same);
    const { expr } = pair;

    return (
        <div className={styles.dimBlock}>
            <div className={styles.dimHeader} onClick={() => setOpen((o) => !o)}>
                <span className={styles.dimTitle}>Expression</span>
                <span className={`${styles.dimSame} ${expr.same ? styles.same : styles.diff}`}>
                    {expr.same ? "Identical" : "Different"}
                </span>
                <span className={styles.dimToggle}>{open ? "▲" : "▼"}</span>
            </div>
            {open && (
                <div className={styles.dimBody}>
                    <div className={styles.sideBySide}>
                        <div className={styles.sideBox}>
                            <span className={styles.sideLabel}>{pair.name_a} (normalized)</span>
                            <pre className={expr.same ? styles.codeSame : styles.codeDiff}>
                                {expr.normalized_a}
                            </pre>
                        </div>
                        <div className={styles.sideBox}>
                            <span className={styles.sideLabel}>{pair.name_b} (normalized)</span>
                            <pre className={expr.same ? styles.codeSame : styles.codeDiff}>
                                {expr.normalized_b}
                            </pre>
                        </div>
                    </div>
                    {!expr.same && (
                        <div className={styles.sideBySide} style={{ marginTop: "0.5rem" }}>
                            <div className={styles.sideBox}>
                                <span className={styles.sideLabel}>{pair.name_a} (raw)</span>
                                <pre className={styles.codeDiff}>{expr.raw_a}</pre>
                            </div>
                            <div className={styles.sideBox}>
                                <span className={styles.sideLabel}>{pair.name_b} (raw)</span>
                                <pre className={styles.codeDiff}>{expr.raw_b}</pre>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Window diff
// ---------------------------------------------------------------------------

function WindowBlock({ pair }: { pair: PairComparison }) {
    const [open, setOpen] = useState(!pair.window.same);
    const { window } = pair;
    const noSpecs = window.specs_a.length === 0 && window.specs_b.length === 0;

    return (
        <div className={styles.dimBlock}>
            <div className={styles.dimHeader} onClick={() => setOpen((o) => !o)}>
                <span className={styles.dimTitle}>Window / Time Intelligence</span>
                {noSpecs ? (
                    <span className={`${styles.dimSame} ${styles.na}`}>None</span>
                ) : (
                    <span className={`${styles.dimSame} ${window.same ? styles.same : styles.diff}`}>
                        {window.same ? "Identical" : `${window.field_diffs.length} diff${window.field_diffs.length !== 1 ? "s" : ""}`}
                    </span>
                )}
                <span className={styles.dimToggle}>{open ? "▲" : "▼"}</span>
            </div>
            {open && (
                <div className={styles.dimBody}>
                    {noSpecs ? (
                        <span className={styles.noneText}>Neither measure has window specs.</span>
                    ) : (
                        <table className={styles.windowTable}>
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Field</th>
                                    <th>{pair.name_a}</th>
                                    <th>{pair.name_b}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {window.field_diffs.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} className={styles.cellSame} style={{ textAlign: "center" }}>
                                            All window fields match
                                        </td>
                                    </tr>
                                ) : (
                                    window.field_diffs.map((d, i) => (
                                        <tr key={i}>
                                            <td>{d.spec_index + 1}</td>
                                            <td>{d.field}</td>
                                            <td className={styles.cellDiff}>
                                                {d.value_a ?? <span className={styles.noneText}>—</span>}
                                            </td>
                                            <td className={styles.cellDiff}>
                                                {d.value_b ?? <span className={styles.noneText}>—</span>}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Lineage diff — Cytoscape graph with per-measure coloured edges
// ---------------------------------------------------------------------------

function LineageBlock({
    pair,
    measures,
    colors,
}: {
    pair: PairComparison;
    measures: Measure[];
    colors: string[];
}) {
    const [open, setOpen] = useState(true);
    const { lineage } = pair;
    const noLineage =
        lineage.leaf_sources_a.length === 0 && lineage.leaf_sources_b.length === 0;

    // Build GraphMeasure objects for the two measures in this pair
    const mA = measures.find((m) => m.id === pair.id_a);
    const mB = measures.find((m) => m.id === pair.id_b);
    const idxA = measures.findIndex((m) => m.id === pair.id_a);
    const idxB = measures.findIndex((m) => m.id === pair.id_b);

    const graphMeasures = [
        mA && {
            id: pair.id_a,
            name: pair.name_a,
            expr: mA.expr,
            metric_view: pair.view_a,
            lineage: mA.lineage,
            window: mA.window,
        },
        mB && {
            id: pair.id_b,
            name: pair.name_b,
            expr: mB.expr,
            metric_view: pair.view_b,
            lineage: mB.lineage,
            window: mB.window,
        },
    ].filter(Boolean) as { id: string; name: string; expr: string; metric_view: string; lineage: Measure["lineage"]; window: Measure["window"] }[];

    const graphColors = [
        colors[idxA % colors.length],
        colors[idxB % colors.length],
    ];

    const statusLabel = noLineage
        ? "No lineage data"
        : lineage.leaves_same
            ? `${lineage.shared_leaves.length} shared sources`
            : `${lineage.only_in_a.length} only-A · ${lineage.shared_leaves.length} shared · ${lineage.only_in_b.length} only-B`;

    return (
        <div className={styles.dimBlock}>
            <div className={styles.dimHeader} onClick={() => setOpen((o) => !o)}>
                <span className={styles.dimTitle}>Lineage</span>
                {noLineage ? (
                    <span className={`${styles.dimSame} ${styles.na}`}>No lineage data</span>
                ) : (
                    <span className={`${styles.dimSame} ${lineage.leaves_same ? styles.same : styles.diff}`}>
                        {statusLabel}
                    </span>
                )}
                <span className={styles.dimToggle}>{open ? "▲" : "▼"}</span>
            </div>
            {open && (
                <div className={styles.dimBody}>
                    {noLineage ? (
                        <span className={styles.noneText}>
                            No lineage was collected for these measures. Run collection with lineage enabled.
                        </span>
                    ) : (
                        <LineageGraph
                            measures={graphMeasures}
                            measureColors={graphColors}
                            height={360}
                        />
                    )}
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Single pair card
// ---------------------------------------------------------------------------

function PairCard({
    pair,
    measures,
    colors,
}: {
    pair: PairComparison;
    measures: Measure[];
    colors: string[];
}) {
    const idxA = measures.findIndex((m) => m.id === pair.id_a);
    const idxB = measures.findIndex((m) => m.id === pair.id_b);

    return (
        <div className={styles.pairSection}>
            <div className={styles.pairHeader}>
                <span
                    className={styles.pairColorBar}
                    style={{ background: `linear-gradient(90deg, ${colors[idxA % colors.length]} 50%, ${colors[idxB % colors.length]} 50%)` }}
                />
                <h3 className={styles.pairTitle}>
                    <span style={{ color: colors[idxA % colors.length] }}>{pair.name_a}</span>
                    <span style={{ color: "#6c757d", fontWeight: 400 }}> vs </span>
                    <span style={{ color: colors[idxB % colors.length] }}>{pair.name_b}</span>
                </h3>
                <span
                    className={`${styles.scoreBadge} ${labelClass(pair.label)}`}
                >
                    {pair.label}
                </span>
                <span
                    className={styles.scoreValue}
                    style={{ color: scoreColor(pair.score) }}
                >
                    {(pair.score * 100).toFixed(0)}% similar
                </span>
            </div>

            <div className={styles.pairBody}>
                <ExprBlock pair={pair} />
                <WindowBlock pair={pair} />
                <LineageBlock pair={pair} measures={measures} colors={colors} />
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// CompareView (modal)
// ---------------------------------------------------------------------------

interface Props {
    selectedIds: string[];
    result: CompareResult | null;
    status: "idle" | "loading" | "success" | "error";
    error: string | null;
    onClose: () => void;
}

export function CompareView({ selectedIds, result, status, error, onClose }: Props) {
    return (
        <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className={styles.modal} role="dialog" aria-modal="true" aria-label="Measure comparison">
                <div className={styles.modalHeader}>
                    <h2 className={styles.modalTitle}>
                        Measure Comparison
                        {result && ` — ${result.measures.length} measures, ${result.pairs.length} pair${result.pairs.length !== 1 ? "s" : ""}`}
                    </h2>
                    <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
                </div>

                {status === "loading" && (
                    <div className={styles.loadingState}>Comparing measures…</div>
                )}

                {status === "error" && (
                    <div className={styles.errorState}>{error}</div>
                )}

                {status === "success" && result && (
                    <div className={styles.modalBody}>
                        <MeasurePills measures={result.measures} />
                        {result.pairs.map((pair) => (
                            <PairCard
                                key={`${pair.id_a}:${pair.id_b}`}
                                pair={pair}
                                measures={result.measures}
                                colors={PILL_COLORS}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
