import type { ConvertRequest, ConvertResult } from "../types/convert";

const BASE_URL = "";

export async function postConvert(request: ConvertRequest): Promise<ConvertResult> {
    const form = new FormData();
    form.append("file", request.file);
    form.append("catalog", request.catalog);
    form.append("schema", request.schema);
    if (request.source_catalog) form.append("source_catalog", request.source_catalog);
    if (request.source_schema) form.append("source_schema", request.source_schema);
    if (request.prefix) form.append("prefix", request.prefix);
    if (request.fact_tables) form.append("fact_tables", request.fact_tables);
    if (request.exclude_tables) form.append("exclude_tables", request.exclude_tables);
    form.append("include_isolated", String(request.include_isolated ?? false));
    form.append("dialect", request.dialect ?? "databricks");

    const res = await fetch(`${BASE_URL}/api/convert`, {
        method: "POST",
        body: form,
    });

    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            detail = body.detail ?? detail;
        } catch {
            // ignore JSON parse failure
        }
        throw new Error(`${res.status}: ${detail}`);
    }

    return res.json() as Promise<ConvertResult>;
}
