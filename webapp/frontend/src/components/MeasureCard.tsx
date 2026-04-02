import { useState } from "react";
import type { Measure } from "../types/measure";
import styles from "./MeasureCard.module.css";
import { LineageGraph, PILL_COLORS } from "./LineageGraph";

interface Props {
    measure: Measure;
    selected?: boolean;
    onToggleSelect?: (id: string) => void;
}

export function MeasureCard({ measure, selected = false, onToggleSelect }: Props) {
    const [expanded, setExpanded] = useState(false);

    return (
        <article className={`${styles.card} ${selected ? styles.cardSelected : ""}`}>
            <div className={styles.header}>
                {onToggleSelect && (
                    <input
                        type="checkbox"
                        className={styles.checkbox}
                        checked={selected}
                        onChange={() => onToggleSelect(measure.id)}
                        title="Select for comparison"
                        onClick={(e) => e.stopPropagation()}
                    />
                )}
                <div className={styles.headerContent} onClick={() => setExpanded((e) => !e)}>
                    <div className={styles.titleRow}>
                        <span className={styles.name}>{measure.name}</span>
                        {measure.display_name && (
                            <span className={styles.displayName}>{measure.display_name}</span>
                        )}
                        <span className={styles.mv}>{measure.metric_view}</span>
                    </div>
                    <code className={styles.expr}>{measure.expr}</code>
                    <span className={styles.expandBtn}>{expanded ? "▲" : "▼"}</span>
                </div>
            </div>

            {expanded && (
                <div className={styles.body}>
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
                </div>
            )}
        </article>
    );
}
