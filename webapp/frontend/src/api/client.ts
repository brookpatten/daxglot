const BASE_URL = "";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`, {
        headers: { "Content-Type": "application/json", ...init?.headers },
        ...init,
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

    return res.json() as Promise<T>;
}
