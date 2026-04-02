import { useMemo, useState } from "react";
import type { Measure, MeasureFilters } from "../types/measure";
import { MeasureCard } from "./MeasureCard";
import styles from "./MeasureList.module.css";

type SortCol = "name" | "metric_view" | null;
type SortDir = "asc" | "desc";

const COL_COUNT = 6;
const PAGE_SIZE = 20;

interface Props {
    measures: Measure[];
    loading: boolean;
    error: string | null;
    selectedIds: Set<string>;
    onToggleSelect: (id: string) => void;
    onCompare: () => void;
    onClearSelection: () => void;
    filters: MeasureFilters;
    onFiltersChange: (f: MeasureFilters) => void;
}

function SortHeader({
    label,
    col,
    sortCol,
    sortDir,
    onSort,
}: {
    label: string;
    col: SortCol;
    sortCol: SortCol;
    sortDir: SortDir;
    onSort: (c: SortCol) => void;
}) {
    const active = sortCol === col;
    return (
        <button
            className={`${styles.sortBtn} ${active ? styles.sortActive : ""}`}
            onClick={() => onSort(col)}
        >
            {label}
            <span className={styles.sortIcon}>
                {active ? (sortDir === "asc" ? " ▲" : " ▼") : " ⇅"}
            </span>
        </button>
    );
}

export function MeasureList({
    measures,
    loading,
    error,
    selectedIds,
    onToggleSelect,
    onCompare,
    onClearSelection,
    filters,
    onFiltersChange,
}: Props) {
    const [sortCol, setSortCol] = useState<SortCol>(null);
    const [sortDir, setSortDir] = useState<SortDir>("asc");
    const [page, setPage] = useState(1);

    function handleSort(col: SortCol) {
        if (sortCol === col) {
            setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        } else {
            setSortCol(col);
            setSortDir("asc");
        }
        setPage(1);
    }

    function handleFilterChange(key: keyof MeasureFilters, value: string) {
        onFiltersChange({ ...filters, [key]: value || undefined });
        setPage(1);
    }

    const sorted = useMemo(() => {
        if (!sortCol) return measures;
        return [...measures].sort((a, b) => {
            const av = a[sortCol] ?? "";
            const bv = b[sortCol] ?? "";
            const cmp = av.localeCompare(bv);
            return sortDir === "asc" ? cmp : -cmp;
        });
    }, [measures, sortCol, sortDir]);

    const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
    const paginated = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

    if (loading) {
        return <div className={styles.state}>Loading…</div>;
    }

    if (error) {
        return <div className={`${styles.state} ${styles.error}`}>{error}</div>;
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

            <div className={styles.tableWrap}>
                <table className={styles.table}>
                    <thead>
                        <tr>
                            <th className={styles.thCheck}></th>
                            <th className={styles.thName}>
                                <SortHeader
                                    label="Name"
                                    col="name"
                                    sortCol={sortCol}
                                    sortDir={sortDir}
                                    onSort={handleSort}
                                />
                                <input
                                    className={styles.filterInput}
                                    type="text"
                                    placeholder="Filter…"
                                    value={filters.name ?? ""}
                                    onChange={(e) => handleFilterChange("name", e.target.value)}
                                />
                            </th>
                            <th className={styles.thDisplay}>Display Name</th>
                            <th className={styles.thMv}>
                                <SortHeader
                                    label="Metric View"
                                    col="metric_view"
                                    sortCol={sortCol}
                                    sortDir={sortDir}
                                    onSort={handleSort}
                                />
                                <input
                                    className={styles.filterInput}
                                    type="text"
                                    placeholder="Filter…"
                                    value={filters.metric_view ?? ""}
                                    onChange={(e) =>
                                        handleFilterChange("metric_view", e.target.value)
                                    }
                                />
                            </th>
                            <th className={styles.thExpr}>
                                <div className={styles.exprHeaderLabel}>Expression</div>
                                <div className={styles.exprFilters}>
                                    {(
                                        [
                                            {
                                                key: "function" as keyof MeasureFilters,
                                                ph: "Function",
                                            },
                                            {
                                                key: "catalog" as keyof MeasureFilters,
                                                ph: "Catalog",
                                            },
                                            {
                                                key: "schema" as keyof MeasureFilters,
                                                ph: "Schema",
                                            },
                                            { key: "table" as keyof MeasureFilters, ph: "Table" },
                                            {
                                                key: "column" as keyof MeasureFilters,
                                                ph: "Column",
                                            },
                                        ] as const
                                    ).map(({ key, ph }) => (
                                        <input
                                            key={key}
                                            className={styles.filterInput}
                                            type="text"
                                            placeholder={ph}
                                            value={filters[key] ?? ""}
                                            onChange={(e) =>
                                                handleFilterChange(key, e.target.value)
                                            }
                                        />
                                    ))}
                                </div>
                            </th>
                            <th className={styles.thExpand}></th>
                        </tr>
                    </thead>
                    <tbody>
                        {paginated.length === 0 ? (
                            <tr>
                                <td colSpan={COL_COUNT} className={styles.emptyCell}>
                                    No measures found.
                                </td>
                            </tr>
                        ) : (
                            paginated.map((m) => (
                                <MeasureCard
                                    key={m.id}
                                    measure={m}
                                    selected={selectedIds.has(m.id)}
                                    onToggleSelect={onToggleSelect}
                                    colCount={COL_COUNT}
                                />
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {totalPages > 1 && (
                <div className={styles.pager}>
                    <button
                        className={styles.pageBtn}
                        disabled={page === 1}
                        onClick={() => setPage(1)}
                    >
                        «
                    </button>
                    <button
                        className={styles.pageBtn}
                        disabled={page === 1}
                        onClick={() => setPage((p) => p - 1)}
                    >
                        ‹
                    </button>
                    <span className={styles.pageInfo}>
                        Page {page} of {totalPages}
                    </span>
                    <button
                        className={styles.pageBtn}
                        disabled={page === totalPages}
                        onClick={() => setPage((p) => p + 1)}
                    >
                        ›
                    </button>
                    <button
                        className={styles.pageBtn}
                        disabled={page === totalPages}
                        onClick={() => setPage(totalPages)}
                    >
                        »
                    </button>
                </div>
            )}
        </div>
    );
}

