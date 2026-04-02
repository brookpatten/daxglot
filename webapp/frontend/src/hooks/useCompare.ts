import { useCallback, useState } from "react";
import { postCompare } from "../api/compare";
import type { CompareResult } from "../types/compare";

type CompareStatus = "idle" | "loading" | "success" | "error";

export function useCompare() {
    const [status, setStatus] = useState<CompareStatus>("idle");
    const [result, setResult] = useState<CompareResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const compare = useCallback(async (ids: string[]) => {
        setStatus("loading");
        setResult(null);
        setError(null);
        try {
            const data = await postCompare(ids);
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

    return { status, result, error, compare, reset };
}
