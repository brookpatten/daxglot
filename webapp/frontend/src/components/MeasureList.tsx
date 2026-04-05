import { useMemo, useState } from "react";
import type { Measure, MeasureFilters } from "../types/measure";
import type { SimilarResult } from "../types/similar";
import { MeasureCard } from "./MeasureCard";
import styles from "./MeasureList.module.css";

type SortCol = "name" | "metric_view" | null;
type SortDir = "asc" | "desc";

const COL_COUNT = 5;
const PAGE_SIZE = 20;

interface SimilarMode {
    source: Measure | null;
    sourceName: string;
    status: "idle" | "loading" | "success" | "error";
    results: SimilarResult[];
    error: string | null;
}

interface Props {
    measures: Measure[];
    loading: boolean;
    error: string | null;
    selectedIds: Set<string>;
    onToggleSelect: (id: string) => void;
    onCompare: () => void;
    onFindSimilar: (id: string) => void;
    onClearSelection: () => void;
    filters: MeasureFilters;
    onFiltersChange: (f: MeasureFilters) => void;
    similarMode?: SimilarMode;
    onClearSimilar?: () => void;
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
    onFindSimilar,
    onClearSelection,
    filters,
    onFiltersChange,
    similarMode,
    onClearSimilar,
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

    // In similar mode, bypass normal sort/pagination and show source + results
    const inSimilarMode = similarMode && similarMode.status !== "idle";

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
                    {inSimilarMode
                        ? similarMode!.results.length > 0
                            ? `${similarMode!.results.length} similar measure${similarMode!.results.length !== 1 ? "s" : ""}`
                            : measures.length + ` measure${measures.length !== 1 ? "s" : ""}`
                        : `${measures.length} measure${measures.length !== 1 ? "s" : ""}`}
                </p>

                {inSimilarMode && (
                    <div className={styles.similarBanner}>
                        <span className={styles.similarBannerIcon}>🔍</span>
                        <span className={styles.similarBannerText}>
                            Similar to <em>{similarMode!.sourceName}</em>
                        </span>
                        <button
                            className={styles.clearSimilarBtn}
                            onClick={onClearSimilar}
                            aria-label="Clear similar filter"
                        >
                            ✕ Clear
                        </button>
                    </div>
                )}

                {selCount === 2 && (
                    <div className={styles.compareBar}>
                        <span className={styles.selCount}>2 selected</span>
                        <button className={styles.compareBtn} onClick={onCompare}>
                            Compare
                        </button>
                        <button className={styles.clearBtn} onClick={onClearSelection}>
                            Clear
                        </button>
                    </div>
                )}
                {selCount === 1 && !inSimilarMode && (
                    <div className={styles.compareBar}>
                        <span className={styles.selCount}>1 selected</span>
                        <button
                            className={styles.similarBtn}
                            onClick={() => onFindSimilar(Array.from(selectedIds)[0])}
                        >
                            Find Similar
                        </button>
                        <span className={styles.selHint}>or select one more to compare</span>
                        <button className={styles.clearBtn} onClick={onClearSelection}>
                            Clear
                        </button>
                    </div>
                )}
                {selCount === 1 && inSimilarMode && (
                    <div className={styles.compareBar}>
                        <span className={styles.selCount}>1 selected</span>
                        <span className={styles.selHint}>select one more to compare</span>
                        <button className={styles.clearBtn} onClick={onClearSelection}>
                            Clear
                        </button>
                    </div>
                )}
            </div>

            <div className={styles.tableWrap}>
                <table className={styles.table}>
                    <thead>
                        <tr>
                            <th className={styles.thCheck}></th>
                            <th className={styles.thDisplay}>
                                <SortHeader
                                    label="Display Name"
                                    col="name"
                                    sortCol={sortCol}
                                    sortDir={sortDir}
                                    onSort={handleSort}
                                />
                                <input
                                    className={styles.filterInput}
                                    type="text"
                                    placeholder="Filter…"
                                    value={filters.display_name ?? ""}
                                    onChange={(e) => handleFilterChange("display_name", e.target.value)}
                                />
                            </th>
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
                        {inSimilarMode ? (
                            similarMode!.status === "loading" ? (
                                <tr className={styles.similarLoadingRow}>
                                    <td colSpan={COL_COUNT}>Searching for similar measures…</td>
                                </tr>
                            ) : similarMode!.status === "error" ? (
                                <tr className={styles.similarErrorRow}>
                                    <td colSpan={COL_COUNT}>{similarMode!.error}</td>
                                </tr>
                            ) : similarMode!.results.length === 0 ? (
                                <tr>
                                    <td colSpan={COL_COUNT} className={styles.emptyCell}>
                                        No similar measures found.
                                    </td>
                                </tr>
                            ) : (
                                <>
                                    {similarMode!.source && (
                                        <MeasureCard
                                            key={similarMode!.source.id}
                                            measure={similarMode!.source}
                                            selected={selectedIds.has(similarMode!.source.id)}
                                            onToggleSelect={onToggleSelect}
                                            selectDisabled={selCount === 2 && !selectedIds.has(similarMode!.source.id)}
                                            colCount={COL_COUNT}
                                            isSource
                                        />
                                    )}
                                    {similarMode!.results.map(({ score, label, measure }) => (
                                        <MeasureCard
                                            key={measure.id}
                                            measure={measure}
                                            selected={selectedIds.has(measure.id)}
                                            onToggleSelect={onToggleSelect}
                                            selectDisabled={selCount === 2 && !selectedIds.has(measure.id)}
                                            colCount={COL_COUNT}
                                            similarScore={{ score, label }}
                                        />
                                    ))}
                                </>
                            )
                        ) : paginated.length === 0 ? (
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
                                    selectDisabled={selCount === 2 && !selectedIds.has(m.id)}
                                    colCount={COL_COUNT}
                                />
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {!inSimilarMode && totalPages > 1 && (
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

