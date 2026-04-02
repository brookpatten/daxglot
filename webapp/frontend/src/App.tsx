import { useState } from "react";
import { CollectPanel } from "./components/CollectPanel";
import { ConvertPanel } from "./components/ConvertPanel";
import { MeasureList } from "./components/MeasureList";
import { SearchFilters } from "./components/SearchFilters";
import { useMeasures } from "./hooks/useMeasures";
import type { MeasureFilters } from "./types/measure";
import styles from "./App.module.css";

export default function App() {
    const [filters, setFilters] = useState<MeasureFilters>({});
    const { measures, loading, error, refresh } = useMeasures(filters);

    return (
        <div className={styles.layout}>
            <header className={styles.header}>
                <h1 className={styles.title}>Measures Explorer</h1>
            </header>
            <main className={styles.main}>
                <ConvertPanel />
                <CollectPanel onCollected={refresh} />
                <SearchFilters filters={filters} onChange={setFilters} />
                <MeasureList measures={measures} loading={loading} error={error} />
            </main>
        </div>
    );
}
