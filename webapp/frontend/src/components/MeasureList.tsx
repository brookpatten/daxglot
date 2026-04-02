import type { Measure } from "../types/measure";
import { MeasureCard } from "./MeasureCard";
import styles from "./MeasureList.module.css";

interface Props {
    measures: Measure[];
    loading: boolean;
    error: string | null;
}

export function MeasureList({ measures, loading, error }: Props) {
    if (loading) {
        return <div className={styles.state}>Loading…</div>;
    }

    if (error) {
        return <div className={`${styles.state} ${styles.error}`}>{error}</div>;
    }

    if (measures.length === 0) {
        return <div className={styles.state}>No measures found.</div>;
    }

    return (
        <div>
            <p className={styles.count}>
                {measures.length} measure{measures.length !== 1 ? "s" : ""}
            </p>
            {measures.map((m) => (
                <MeasureCard key={m.id} measure={m} />
            ))}
        </div>
    );
}
