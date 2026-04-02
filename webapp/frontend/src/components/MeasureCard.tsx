import { useState } from "react";
import type { LineageColumn, Measure } from "../types/measure";
import styles from "./MeasureCard.module.css";

interface Props {
    measure: Measure;
}

function LineageTree({ nodes, depth = 0 }: { nodes: LineageColumn[]; depth?: number }) {
    if (nodes.length === 0) return null;
    return (
        <ul className={styles.lineageList} style={{ paddingLeft: depth === 0 ? 0 : "1.2rem" }}>
            {nodes.map((node, i) => (
                <li key={i} className={styles.lineageNode}>
                    <span className={styles.lineageTable}>{node.table}</span>
                    <span className={styles.lineageCol}>.{node.column}</span>
                    <span className={styles.lineageType}>[{node.type}]</span>
                    {node.upstream.length > 0 && (
                        <LineageTree nodes={node.upstream} depth={depth + 1} />
                    )}
                </li>
            ))}
        </ul>
    );
}

export function MeasureCard({ measure }: Props) {
    const [expanded, setExpanded] = useState(false);

    return (
        <article className={styles.card}>
            <div className={styles.header} onClick={() => setExpanded((e) => !e)}>
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
                            <LineageTree nodes={measure.lineage} />
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
