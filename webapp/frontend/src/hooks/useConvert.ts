import { useCallback, useState } from "react";
import { postConvert } from "../api/convert";
import type { ConvertRequest, ConvertResult } from "../types/convert";

type ConvertStatus = "idle" | "loading" | "success" | "error";

export function useConvert() {
    const [status, setStatus] = useState<ConvertStatus>("idle");
    const [result, setResult] = useState<ConvertResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const convert = useCallback(async (request: ConvertRequest) => {
        setStatus("loading");
        setResult(null);
        setError(null);
        try {
            const data = await postConvert(request);
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

    return { status, result, error, convert, reset };
}
