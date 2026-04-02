import type { MeasureFilters } from "../types/measure";
import styles from "./SearchFilters.module.css";

interface Props {
    filters: MeasureFilters;
    onChange: (f: MeasureFilters) => void;
}

const FIELDS: { key: keyof MeasureFilters; label: string; placeholder: string }[] = [
    { key: "name", label: "Name", placeholder: "e.g. Monthly_Sales" },
    { key: "metric_view", label: "Metric view", placeholder: "e.g. country_sales" },
    { key: "function", label: "Function", placeholder: "e.g. SUM" },
    { key: "catalog", label: "Catalog", placeholder: "e.g. prod" },
    { key: "schema", label: "Schema", placeholder: "e.g. finance" },
    { key: "table", label: "Table", placeholder: "e.g. fact_orders" },
    { key: "column", label: "Column", placeholder: "e.g. total" },
];

export function SearchFilters({ filters, onChange }: Props) {
    function handleChange(key: keyof MeasureFilters, value: string) {
        onChange({ ...filters, [key]: value || undefined });
    }

    function handleClear() {
        onChange({});
    }

    const hasFilters = Object.values(filters).some((v) => v !== undefined && v !== "");

    return (
        <div className={styles.container}>
            <div className={styles.grid}>
                {FIELDS.map(({ key, label, placeholder }) => (
                    <label key={key} className={styles.field}>
                        <span>{label}</span>
                        <input
                            type="text"
                            value={filters[key] ?? ""}
                            placeholder={placeholder}
                            onChange={(e) => handleChange(key, e.target.value)}
                        />
                    </label>
                ))}
            </div>
            {hasFilters && (
                <button className={styles.clear} onClick={handleClear}>
                    Clear filters
                </button>
            )}
        </div>
    );
}
