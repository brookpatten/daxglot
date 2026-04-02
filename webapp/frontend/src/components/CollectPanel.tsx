import { useState } from "react";
import { useCollect } from "../hooks/useCollect";
import styles from "./CollectPanel.module.css";

interface Props {
    onCollected: () => void;
}

export function CollectPanel({ onCollected }: Props) {
    const [open, setOpen] = useState(false);
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
        <section className={styles.panel}>
            <button className={styles.toggle} onClick={() => setOpen((o) => !o)}>
                {open ? "▲ Collection" : "▼ Collect from Databricks"}
            </button>

            {open && (
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
            )}
        </section>
    );
}
