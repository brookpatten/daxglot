import { useState } from "react";
import type { Measure } from "../types/measure";
import styles from "./MeasureCard.module.css";
import { LineageGraph, PILL_COLORS } from "./LineageGraph";

interface SimilarScore {
    score: number;
    label: "Identical" | "Similar" | "Different";
}

interface Props {
    measure: Measure;
    selected?: boolean;
    onToggleSelect?: (id: string) => void;
    selectDisabled?: boolean;
    colCount: number;
    isSource?: boolean;
    similarScore?: SimilarScore;
}

export function MeasureCard({ measure, selected = false, onToggleSelect, selectDisabled = false, colCount, isSource, similarScore }: Props) {
    const [expanded, setExpanded] = useState(false);

    const pct = similarScore ? Math.round(similarScore.score * 100) : null;
    const badgeCls = similarScore
        ? similarScore.label === "Identical"
            ? styles.badgeIdentical
            : similarScore.label === "Similar"
                ? styles.badgeSimilar
                : styles.badgeDifferent
        : null;

    const rowCls = [
        styles.row,
        selected ? styles.rowSelected : "",
        isSource ? styles.rowSource : "",
    ].filter(Boolean).join(" ");

    return (
        <>
            <tr className={rowCls}>
                <td className={styles.checkCell}>
                    {onToggleSelect && (
                        <input
                            type="checkbox"
                            className={styles.checkbox}
                            checked={selected}
                            disabled={selectDisabled}
                            onChange={() => onToggleSelect(measure.id)}
                            title={selectDisabled ? "Deselect a measure before selecting another" : "Select for comparison"}
                        />
                    )}
                </td>
                <td className={styles.displayNameCell}>
                    <span className={styles.displayName}>{measure.display_name ?? measure.name}</span>
                    {(isSource || similarScore) && (
                        <div className={styles.nameBadges}>
                            {isSource && <span className={styles.sourceBadge}>Reference</span>}
                            {similarScore && pct !== null && badgeCls && (
                                <span className={`${styles.scoreBadge} ${badgeCls}`}>
                                    {pct}% · {similarScore.label}
                                </span>
                            )}
                        </div>
                    )}
                </td>
                <td className={styles.mvCell}>
                    <span className={styles.mv}>{measure.metric_view}</span>
                </td>
                <td className={styles.exprCell}>
                    <code className={styles.expr}>{measure.expr}</code>
                </td>
                <td className={styles.expandCell} onClick={() => setExpanded((e) => !e)}>
                    <span className={styles.expandBtn}>{expanded ? "▲" : "▼"}</span>
                </td>
            </tr>

            {expanded && (
                <tr className={styles.detailRow}>
                    <td colSpan={colCount} className={styles.detailCell}>
                        {measure.comment && <p className={styles.comment}>{measure.comment}</p>}

                        {measure.window.length > 0 && (
                            <div className={styles.section}>
                                <h4>Window specs</h4>
                                <ul>
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
                            <div className={styles.section}>
                                <h4>Referenced measures</h4>
                                <ul>
                                    {measure.referenced_measures.map((ref, i) => (
                                        <li key={i}><code>{ref}</code></li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {measure.lineage.length > 0 && (
                            <div className={styles.section}>
                                <h4>Lineage</h4>
                                <LineageGraph
                                    measures={[{
                                        id: measure.id,
                                        name: measure.name,
                                        expr: measure.expr,
                                        metric_view: measure.metric_view,
                                        source_table: measure.source_table,
                                        dimensions: measure.dimensions,
                                        lineage: measure.lineage,
                                        window: measure.window,
                                    }]}
                                    measureColors={[PILL_COLORS[0]]}
                                    height={280}
                                />
                            </div>
                        )}

                        {measure.lineage.length === 0 && measure.window.length === 0 && measure.referenced_measures.length === 0 && (
                            <p className={styles.noExtra}>No additional details.</p>
                        )}
                    </td>
                </tr>
            )}
        </>
    );
}
