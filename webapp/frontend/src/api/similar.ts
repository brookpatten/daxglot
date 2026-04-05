import type { SimilarResult } from "../types/similar";
import { apiFetch } from "./client";

export function fetchSimilar(id: string): Promise<SimilarResult[]> {
    return apiFetch<SimilarResult[]>(`/api/similar?id=${encodeURIComponent(id)}`);
}
