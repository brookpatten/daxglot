import type { CollectRequest, CollectResult } from "../types/measure";
import { apiFetch } from "./client";

export function postCollect(request: CollectRequest): Promise<CollectResult> {
    return apiFetch<CollectResult>("/api/collect", {
        method: "POST",
        body: JSON.stringify(request),
    });
}
