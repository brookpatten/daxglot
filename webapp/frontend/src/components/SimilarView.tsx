import type { SimilarResult } from "../types/similar";
import styles from "./SimilarView.module.css";

interface Props {
    sourceName: string;
    results: SimilarResult[];
    status: "idle" | "loading" | "success" | "error";
    error: string | null;
    onClose: () => void;
}

function ScoreBadge({ score, label }: { score: number; label: string }) {
    const pct = Math.round(score * 100);
    const cls =
        label === "Identical"
            ? styles.badgeIdentical
            : label === "Similar"
                ? styles.badgeSimilar
                : styles.badgeDifferent;
    return (
        <span className={`${styles.badge} ${cls}`}>
            {pct}%
        </span>
    );
}

export function SimilarView({ sourceName, results, status, error, onClose }: Props) {
    return (
        <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className={styles.modal}>
                <div className={styles.modalHeader}>
                    <h2 className={styles.modalTitle}>
                        Measures similar to <em>{sourceName}</em>
                    </h2>
                    <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
                        ✕
                    </button>
                </div>

                <div className={styles.body}>
                    {status === "loading" && (
                        <div className={styles.state}>Searching…</div>
                    )}
                    {status === "error" && (
                        <div className={`${styles.state} ${styles.errorState}`}>{error}</div>
                    )}
                    {status === "success" && results.length === 0 && (
                        <div className={styles.state}>No other measures found.</div>
                    )}
                    {status === "success" && results.length > 0 && (
                        <table className={styles.table}>
                            <thead>
                                <tr>
                                    <th className={styles.thScore}>Score</th>
                                    <th className={styles.thName}>Name</th>
                                    <th className={styles.thMv}>Metric View</th>
                                    <th className={styles.thExpr}>Expression</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results.map(({ score, label, measure }) => (
                                    <tr key={measure.id} className={styles.row}>
                                        <td className={styles.tdScore}>
                                            <ScoreBadge score={score} label={label} />
                                        </td>
                                        <td className={styles.tdName}>
                                            <span className={styles.name}>{measure.name}</span>
                                            {measure.display_name && (
                                                <span className={styles.displayName}>
                                                    {measure.display_name}
                                                </span>
                                            )}
                                        </td>
                                        <td className={styles.tdMv}>{measure.metric_view}</td>
                                        <td className={styles.tdExpr}>
                                            <code className={styles.expr}>{measure.expr}</code>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>
        </div>
    );
}
