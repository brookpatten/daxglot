import { useCallback, useState } from "react";
import { fetchSimilar } from "../api/similar";
import type { SimilarResult } from "../types/similar";

type SimilarStatus = "idle" | "loading" | "success" | "error";

export function useSimilar() {
    const [status, setStatus] = useState<SimilarStatus>("idle");
    const [results, setResults] = useState<SimilarResult[]>([]);
    const [error, setError] = useState<string | null>(null);

    const findSimilar = useCallback(async (id: string) => {
        setStatus("loading");
        setResults([]);
        setError(null);
        try {
            const data = await fetchSimilar(id);
            setResults(data);
            setStatus("success");
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : String(err));
            setStatus("error");
        }
    }, []);

    const reset = useCallback(() => {
        setStatus("idle");
        setResults([]);
        setError(null);
    }, []);

    return { status, results, error, findSimilar, reset };
}
