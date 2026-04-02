import { useCallback, useEffect, useRef, useState } from "react";
import { fetchMeasures } from "../api/measures";
import type { Measure, MeasureFilters } from "../types/measure";

export function useMeasures(filters: MeasureFilters, debounceMs = 300) {
    const [measures, setMeasures] = useState<Measure[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const doFetch = useCallback((f: MeasureFilters) => {
        setLoading(true);
        setError(null);
        fetchMeasures(f)
            .then((data) => {
                setMeasures(data);
            })
            .catch((err: unknown) => {
                setError(err instanceof Error ? err.message : String(err));
            })
            .finally(() => {
                setLoading(false);
            });
    }, []);

    useEffect(() => {
        if (timerRef.current !== null) clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => doFetch(filters), debounceMs);
        return () => {
            if (timerRef.current !== null) clearTimeout(timerRef.current);
        };
    }, [filters, debounceMs, doFetch]);

    const refresh = useCallback(() => doFetch(filters), [filters, doFetch]);

    return { measures, loading, error, refresh };
}
