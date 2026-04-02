import type { CompareResult } from "../types/compare";
import { apiFetch } from "./client";

export function postCompare(ids: string[]): Promise<CompareResult> {
    return apiFetch<CompareResult>("/api/compare", {
        method: "POST",
        body: JSON.stringify({ ids }),
    });
}
