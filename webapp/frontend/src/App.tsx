import { useState } from "react";
import { CollectPanel } from "./components/CollectPanel";
import { CompareView } from "./components/CompareView";
import { ConvertPanel } from "./components/ConvertPanel";
import { MeasureList } from "./components/MeasureList";
import { SearchFilters } from "./components/SearchFilters";
import { useCompare } from "./hooks/useCompare";
import { useMeasures } from "./hooks/useMeasures";
import type { MeasureFilters } from "./types/measure";
import styles from "./App.module.css";

export default function App() {
    const [filters, setFilters] = useState<MeasureFilters>({});
    const { measures, loading, error, refresh } = useMeasures(filters);

    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [compareOpen, setCompareOpen] = useState(false);
    const [collectOpen, setCollectOpen] = useState(false);
    const [convertOpen, setConvertOpen] = useState(false);
    const { status: cmpStatus, result: cmpResult, error: cmpError, compare, reset: resetCompare } = useCompare();

    function handleToggleSelect(id: string) {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    }

    function handleCompare() {
        setCompareOpen(true);
        compare(Array.from(selectedIds));
    }

    function handleCloseCompare() {
        setCompareOpen(false);
        resetCompare();
    }

    return (
        <div className={styles.layout}>
            <header className={styles.header}>
                <h1 className={styles.title}>Measure Governance</h1>
                <div className={styles.headerActions}>
                    <button className={styles.headerBtn} onClick={() => setConvertOpen(true)}>
                        Import From PowerBI
                    </button>
                    <button className={styles.headerBtn} onClick={() => setCollectOpen(true)}>
                        Import From Databricks
                    </button>
                </div>
            </header>
            <main className={styles.main}>
                <SearchFilters filters={filters} onChange={setFilters} />
                <MeasureList
                    measures={measures}
                    loading={loading}
                    error={error}
                    selectedIds={selectedIds}
                    onToggleSelect={handleToggleSelect}
                    onCompare={handleCompare}
                    onClearSelection={() => setSelectedIds(new Set())}
                />
            </main>

            {compareOpen && (
                <CompareView
                    selectedIds={Array.from(selectedIds)}
                    result={cmpResult}
                    status={cmpStatus}
                    error={cmpError}
                    onClose={handleCloseCompare}
                />
            )}
            {convertOpen && <ConvertPanel onClose={() => setConvertOpen(false)} />}
            {collectOpen && <CollectPanel onCollected={refresh} onClose={() => setCollectOpen(false)} />}
        </div>
    );
}
