import { useState } from "react";
import type { Measure } from "../types/measure";
import type { CompareResult, LeafSource, PairComparison } from "../types/compare";
import styles from "./CompareView.module.css";

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
// Lineage diff — venn-style three columns
// ---------------------------------------------------------------------------

function LeafChip({ leaf, variant }: { leaf: LeafSource; variant: "shared" | "only" }) {
    return (
        <div
            className={`${styles.leafChip} ${variant === "shared" ? styles.leafShared : styles.leafOnly}`}
            title={`${leaf.table}.${leaf.column}`}
        >
            <span style={{ opacity: 0.65 }}>{leaf.table.split(".").slice(-1)[0]}</span>
            <span style={{ fontWeight: 600 }}>.{leaf.column}</span>
        </div>
    );
}

function LineageBlock({ pair }: { pair: PairComparison }) {
    const [open, setOpen] = useState(true);
    const { lineage } = pair;
    const noLineage =
        lineage.leaf_sources_a.length === 0 && lineage.leaf_sources_b.length === 0;

    return (
        <div className={styles.dimBlock}>
            <div className={styles.dimHeader} onClick={() => setOpen((o) => !o)}>
                <span className={styles.dimTitle}>Lineage (leaf sources)</span>
                {noLineage ? (
                    <span className={`${styles.dimSame} ${styles.na}`}>No lineage data</span>
                ) : (
                    <span className={`${styles.dimSame} ${lineage.leaves_same ? styles.same : styles.diff}`}>
                        {lineage.leaves_same
                            ? `${lineage.shared_leaves.length} shared`
                            : `${lineage.only_in_a.length} only-A · ${lineage.shared_leaves.length} shared · ${lineage.only_in_b.length} only-B`}
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
                        <>
                            <div className={styles.lineageGrid}>
                                {/* Only in A */}
                                <div className={styles.lineageCol}>
                                    <span className={styles.lineageColTitle}>
                                        Only in {pair.name_a}
                                    </span>
                                    {lineage.only_in_a.length === 0 ? (
                                        <span className={styles.leafEmpty}>—</span>
                                    ) : (
                                        lineage.only_in_a.map((l, i) => (
                                            <LeafChip key={i} leaf={l} variant="only" />
                                        ))
                                    )}
                                    {lineage.has_extra_hops_a && (
                                        <span className={styles.hopsNote}>
                                            ↳ extra intermediate hop(s)
                                        </span>
                                    )}
                                </div>

                                {/* Shared */}
                                <div className={styles.lineageShared}>
                                    <span className={styles.sharedTitle}>Shared</span>
                                    {lineage.shared_leaves.length === 0 ? (
                                        <span className={styles.leafEmpty}>—</span>
                                    ) : (
                                        lineage.shared_leaves.map((l, i) => (
                                            <LeafChip key={i} leaf={l} variant="shared" />
                                        ))
                                    )}
                                </div>

                                {/* Only in B */}
                                <div className={styles.lineageCol}>
                                    <span className={styles.lineageColTitle}>
                                        Only in {pair.name_b}
                                    </span>
                                    {lineage.only_in_b.length === 0 ? (
                                        <span className={styles.leafEmpty}>—</span>
                                    ) : (
                                        lineage.only_in_b.map((l, i) => (
                                            <LeafChip key={i} leaf={l} variant="only" />
                                        ))
                                    )}
                                    {lineage.has_extra_hops_b && (
                                        <span className={styles.hopsNote}>
                                            ↳ extra intermediate hop(s)
                                        </span>
                                    )}
                                </div>
                            </div>
                        </>
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
}: {
    pair: PairComparison;
    measures: Measure[];
}) {
    const mA = measures.find((m) => m.id === pair.id_a);
    const mB = measures.find((m) => m.id === pair.id_b);

    return (
        <div className={styles.pairSection}>
            <div className={styles.pairHeader}>
                <h3 className={styles.pairTitle}>
                    {pair.name_a} vs {pair.name_b}
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
                <LineageBlock pair={pair} />
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
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
