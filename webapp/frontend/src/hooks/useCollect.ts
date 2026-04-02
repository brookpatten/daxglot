import { useCallback, useState } from "react";
import { postCollect } from "../api/collect";
import type { CollectRequest, CollectResult } from "../types/measure";

type CollectStatus = "idle" | "loading" | "success" | "error";

export function useCollect() {
    const [status, setStatus] = useState<CollectStatus>("idle");
    const [result, setResult] = useState<CollectResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const collect = useCallback(async (request: CollectRequest) => {
        setStatus("loading");
        setResult(null);
        setError(null);
        try {
            const data = await postCollect(request);
            setResult(data);
            setStatus("success");
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : String(err));
            setStatus("error");
        }
    }, []);

    const reset = useCallback(() => {
        setStatus("idle");
        setResult(null);
        setError(null);
    }, []);

    return { status, result, error, collect, reset };
}
