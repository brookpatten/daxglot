import { useState } from "react";
import { useCollect } from "../hooks/useCollect";
import styles from "./CollectPanel.module.css";

interface Props {
    onCollected: () => void;
    onClose: () => void;
}

export function CollectPanel({ onCollected, onClose }: Props) {
    const [catalogInput, setCatalogInput] = useState("");
    const [schema, setSchema] = useState("");
    const [view, setView] = useState("");
    const [maxDepth, setMaxDepth] = useState(100);
    const [noLineage, setNoLineage] = useState(false);

    const { status, result, error, collect } = useCollect();

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        const catalogs = catalogInput
            .split(/[,\s]+/)
            .map((s) => s.trim())
            .filter(Boolean);
        collect({ catalogs, schema_: schema || undefined, view: view || undefined, max_depth: maxDepth, no_lineage: noLineage }).then(() => {
            onCollected();
        });
    }

    return (
        <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className={styles.modal}>
                <div className={styles.modalHeader}>
                    <h2 className={styles.modalTitle}>Import From Databricks</h2>
                    <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
                </div>
                <form className={styles.form} onSubmit={handleSubmit}>
                    <div className={styles.row}>
                        <label>
                            Catalogs <span className={styles.hint}>(comma-separated)</span>
                            <input
                                type="text"
                                placeholder="prod, dev"
                                value={catalogInput}
                                onChange={(e) => setCatalogInput(e.target.value)}
                            />
                        </label>
                        <label>
                            Schema
                            <input
                                type="text"
                                placeholder="finance"
                                value={schema}
                                onChange={(e) => setSchema(e.target.value)}
                            />
                        </label>
                        <label>
                            View
                            <input
                                type="text"
                                placeholder="sales_metrics"
                                value={view}
                                onChange={(e) => setView(e.target.value)}
                            />
                        </label>
                    </div>
                    <div className={styles.row}>
                        <label>
                            Max lineage depth
                            <input
                                type="number"
                                min={0}
                                value={maxDepth}
                                onChange={(e) => setMaxDepth(Number(e.target.value))}
                            />
                        </label>
                        <label className={styles.checkLabel}>
                            <input
                                type="checkbox"
                                checked={noLineage}
                                onChange={(e) => setNoLineage(e.target.checked)}
                            />
                            Skip lineage collection
                        </label>
                    </div>
                    <div className={styles.actions}>
                        <button type="submit" disabled={status === "loading"}>
                            {status === "loading" ? "Collecting…" : "Collect"}
                        </button>
                    </div>

                    {status === "success" && result && (
                        <p className={styles.success}>
                            Collected {result.measures_collected} measure{result.measures_collected !== 1 ? "s" : ""}.
                        </p>
                    )}
                    {status === "error" && error && (
                        <p className={styles.error}>{error}</p>
                    )}
                </form>
            </div>
        </div>
    );
}
