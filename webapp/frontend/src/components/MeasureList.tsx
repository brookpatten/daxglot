import type { Measure } from "../types/measure";
import { MeasureCard } from "./MeasureCard";
import styles from "./MeasureList.module.css";

interface Props {
    measures: Measure[];
    loading: boolean;
    error: string | null;
    selectedIds: Set<string>;
    onToggleSelect: (id: string) => void;
    onCompare: () => void;
    onClearSelection: () => void;
}

export function MeasureList({
    measures,
    loading,
    error,
    selectedIds,
    onToggleSelect,
    onCompare,
    onClearSelection,
}: Props) {
    if (loading) {
        return <div className={styles.state}>Loading…</div>;
    }

    if (error) {
        return <div className={`${styles.state} ${styles.error}`}>{error}</div>;
    }

    if (measures.length === 0) {
        return <div className={styles.state}>No measures found.</div>;
    }

    const selCount = selectedIds.size;

    return (
        <div>
            <div className={styles.toolbar}>
                <p className={styles.count}>
                    {measures.length} measure{measures.length !== 1 ? "s" : ""}
                </p>
                {selCount >= 2 && (
                    <div className={styles.compareBar}>
                        <span className={styles.selCount}>{selCount} selected</span>
                        <button className={styles.compareBtn} onClick={onCompare}>
                            Compare {selCount}
                        </button>
                        <button className={styles.clearBtn} onClick={onClearSelection}>
                            Clear
                        </button>
                    </div>
                )}
                {selCount === 1 && (
                    <span className={styles.selHint}>Select one more to compare</span>
                )}
            </div>
            {measures.map((m) => (
                <MeasureCard
                    key={m.id}
                    measure={m}
                    selected={selectedIds.has(m.id)}
                    onToggleSelect={onToggleSelect}
                />
            ))}
        </div>
    );
}
