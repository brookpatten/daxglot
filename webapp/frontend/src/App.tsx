import { useState } from "react";
import { CollectPanel } from "./components/CollectPanel";
import { CompareView } from "./components/CompareView";
import { ConvertPanel } from "./components/ConvertPanel";
import { MeasureList } from "./components/MeasureList";
import { useCompare } from "./hooks/useCompare";
import { useMeasures } from "./hooks/useMeasures";
import { useSimilar } from "./hooks/useSimilar";
import type { Measure, MeasureFilters } from "./types/measure";
import styles from "./App.module.css";

export default function App() {
    const [filters, setFilters] = useState<MeasureFilters>({});
    const { measures, loading, error, refresh } = useMeasures(filters);

    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [compareOpen, setCompareOpen] = useState(false);
    const [collectOpen, setCollectOpen] = useState(false);
    const [convertOpen, setConvertOpen] = useState(false);
    const { status: cmpStatus, result: cmpResult, error: cmpError, compare, reset: resetCompare } = useCompare();

    const [similarSource, setSimilarSource] = useState<Measure | null>(null);
    const [similarSourceName, setSimilarSourceName] = useState("");
    const { status: simStatus, results: simResults, error: simError, findSimilar, reset: resetSimilar } = useSimilar();

    function handleToggleSelect(id: string) {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else if (next.size < 2) {
                next.add(id);
            }
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

    function handleFindSimilar(id: string) {
        const measure = measures.find((m) => m.id === id);
        setSimilarSource(measure ?? null);
        setSimilarSourceName(measure?.name ?? id);
        findSimilar(id);
    }

    function handleClearSimilar() {
        setSimilarSource(null);
        setSimilarSourceName("");
        resetSimilar();
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
                <MeasureList
                    measures={measures}
                    loading={loading}
                    error={error}
                    selectedIds={selectedIds}
                    onToggleSelect={handleToggleSelect}
                    onCompare={handleCompare}
                    onFindSimilar={handleFindSimilar}
                    onClearSelection={() => setSelectedIds(new Set())}
                    filters={filters}
                    onFiltersChange={setFilters}
                    similarMode={simStatus !== "idle" ? {
                        source: similarSource,
                        sourceName: similarSourceName,
                        status: simStatus,
                        results: simResults,
                        error: simError,
                    } : undefined}
                    onClearSimilar={handleClearSimilar}
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
