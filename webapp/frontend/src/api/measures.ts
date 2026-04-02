import type { Measure, MeasureFilters } from "../types/measure";
import { apiFetch } from "./client";

function buildQuery(filters: MeasureFilters): string {
    const params = new URLSearchParams();
    for (const [key, val] of Object.entries(filters)) {
        if (val !== undefined && val !== "") {
            params.set(key, val);
        }
    }
    const qs = params.toString();
    return qs ? `?${qs}` : "";
}

export function fetchMeasures(filters: MeasureFilters = {}): Promise<Measure[]> {
    return apiFetch<Measure[]>(`/api/measures${buildQuery(filters)}`);
}

export function fetchMeasure(id: string): Promise<Measure> {
    return apiFetch<Measure>(`/api/measures/${encodeURIComponent(id)}`);
}
