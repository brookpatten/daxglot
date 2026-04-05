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

// ---------------------------------------------------------------------------
// Per-measure detail columns inside each pair card
// ---------------------------------------------------------------------------

function MeasureDetailColumn({
    measure,
    letterIdx,
    normalizedExpr,
    exprSame,
    colors,
}: {
    measure: Measure;
    letterIdx: number;
    normalizedExpr: string;
    exprSame: boolean;
    colors: string[];
}) {
    const color = colors[letterIdx % colors.length];
    const normalizedDiffersFromRaw = normalizedExpr.trim() !== measure.expr.trim();

    return (
        <div className={styles.detailColumn}>
            <div className={styles.detailColumnHeader}>
                <span className={styles.pillLabel} style={{ background: color }}>
                    {String.fromCharCode(65 + letterIdx)}
                </span>
                <span className={styles.pillName}>{measure.name}</span>
                {measure.display_name && (
                    <span className={styles.detailDisplayName}>{measure.display_name}</span>
                )}
            </div>
            <span className={styles.pillView}>{measure.metric_view}</span>

            <div className={styles.detailSection}>
                <span className={styles.detailSectionLabel}>Expression</span>
                <pre className={exprSame ? styles.codeSame : styles.codeDiff}>{measure.expr}</pre>
            </div>

            {measure.comment && (
                <div className={styles.detailSection}>
                    <span className={styles.detailSectionLabel}>Comment</span>
                    <p className={styles.detailComment}>{measure.comment}</p>
                </div>
            )}

            {measure.window.length > 0 && (
                <div className={styles.detailSection}>
                    <span className={styles.detailSectionLabel}>Window specs</span>
                    <ul className={styles.detailList}>
                        {measure.window.map((w, i) => (
                            <li key={i}>
                                <strong>{w.order}</strong> — {w.range}
                                {w.semiadditive && <em> ({w.semiadditive})</em>}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {measure.referenced_measures.length > 0 && (
                <div className={styles.detailSection}>
                    <span className={styles.detailSectionLabel}>References</span>
                    <ul className={styles.detailList}>
                        {measure.referenced_measures.map((ref, i) => (
                            <li key={i}><code>{ref}</code></li>
                        ))}
                    </ul>
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
            source_table: mA.source_table,
            dimensions: mA.dimensions,
            lineage: mA.lineage,
            window: mA.window,
        },
        mB && {
            id: pair.id_b,
            name: pair.name_b,
            expr: mB.expr,
            metric_view: pair.view_b,
            source_table: mB.source_table,
            dimensions: mB.dimensions,
            lineage: mB.lineage,
            window: mB.window,
        },
    ].filter(Boolean) as { id: string; name: string; expr: string; metric_view: string; source_table: string; dimensions: Measure["dimensions"]; lineage: Measure["lineage"]; window: Measure["window"] }[];

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
    const mA = measures.find((m) => m.id === pair.id_a);
    const mB = measures.find((m) => m.id === pair.id_b);

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
                <span className={`${styles.scoreBadge} ${labelClass(pair.label)}`}>
                    {pair.label}
                </span>
                <span
                    className={styles.scoreValue}
                    style={{ color: scoreColor(pair.score) }}
                >
                    {(pair.score * 100).toFixed(0)}% similar
                </span>
            </div>

            <div className={styles.measureDetailsGrid}>
                {mA && (
                    <MeasureDetailColumn
                        measure={mA}
                        letterIdx={idxA}
                        normalizedExpr={pair.expr.normalized_a}
                        exprSame={pair.expr.same}
                        colors={colors}
                    />
                )}
                {mB && (
                    <MeasureDetailColumn
                        measure={mB}
                        letterIdx={idxB}
                        normalizedExpr={pair.expr.normalized_b}
                        exprSame={pair.expr.same}
                        colors={colors}
                    />
                )}
            </div>

            <div className={styles.pairBody}>
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
