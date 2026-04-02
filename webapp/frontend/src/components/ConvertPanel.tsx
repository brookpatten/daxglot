import { useState } from "react";
import { useConvert } from "../hooks/useConvert";
import type { MeasureConversion, MetricView, MSourceResolution } from "../types/convert";
import styles from "./ConvertPanel.module.css";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MeasureCard({ measure }: { measure: MeasureConversion }) {
    const [open, setOpen] = useState(false);
    return (
        <div className={styles.measureCard}>
            <div className={styles.measureHeader} onClick={() => setOpen((o) => !o)}>
                <span className={styles.measureName}>{measure.name}</span>
                {measure.is_approximate && (
                    <span className={styles.approxBadge}>APPROX</span>
                )}
                {measure.warnings.length > 0 && (
                    <span className={styles.approxBadge} style={{ background: "#fce4ec", color: "#c62828", borderColor: "#ef9a9a" }}>
                        {measure.warnings.length} warn
                    </span>
                )}
                <span>{open ? "▲" : "▼"}</span>
            </div>
            {open && (
                <div className={styles.measureBody}>
                    <div className={styles.codeBlock}>
                        <span className={`${styles.codeLabel} ${styles.dax}`}>DAX</span>
                        <pre className={styles.code}>{measure.dax || "(none)"}</pre>
                    </div>
                    <div className={styles.codeBlock}>
                        <span className={`${styles.codeLabel} ${styles.sql}`}>SQL</span>
                        <pre className={styles.code}>{measure.sql || "(not translated)"}</pre>
                    </div>
                    {measure.warnings.length > 0 && (
                        <ul className={styles.measureWarnings}>
                            {measure.warnings.map((w, i) => <li key={i}>{w}</li>)}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}

function MetricViewCard({ view }: { view: MetricView }) {
    const [open, setOpen] = useState(false);
    const [ddlTab, setDdlTab] = useState<"yaml" | "sql">("yaml");

    return (
        <div className={styles.metricViewCard}>
            <div className={styles.metricViewHeader} onClick={() => setOpen((o) => !o)}>
                <span className={styles.metricViewName}>{view.name}</span>
                <span className={styles.metricViewMeta}>
                    <span>{view.measures.length} measures</span>
                    <span>{view.dimensions_count} dims</span>
                    {view.joins_count > 0 && <span>{view.joins_count} joins</span>}
                </span>
                <span>{open ? "▲" : "▼"}</span>
            </div>
            {open && (
                <div className={styles.metricViewBody}>
                    <p className={styles.metricViewSource}>
                        Source: <code>{view.source_table}</code>
                        {view.source_uc_ref && (
                            <> → <code>{view.source_uc_ref}</code></>
                        )}
                    </p>

                    {view.measures.length > 0 && (
                        <div>
                            <p className={styles.measureListTitle}>
                                Measures ({view.measures.length})
                            </p>
                            <div className={styles.measureList}>
                                {view.measures.map((m) => (
                                    <MeasureCard key={m.name} measure={m} />
                                ))}
                            </div>
                        </div>
                    )}

                    <div className={styles.ddlSection}>
                        <div className={styles.tabBar}>
                            <button
                                className={`${styles.tab} ${ddlTab === "yaml" ? styles.tabActive : ""}`}
                                onClick={() => setDdlTab("yaml")}
                            >
                                YAML
                            </button>
                            <button
                                className={`${styles.tab} ${ddlTab === "sql" ? styles.tabActive : ""}`}
                                onClick={() => setDdlTab("sql")}
                            >
                                SQL DDL
                            </button>
                        </div>
                        <pre className={styles.code}>
                            {ddlTab === "yaml" ? view.yaml_content : view.sql_ddl}
                        </pre>
                    </div>
                </div>
            )}
        </div>
    );
}

function ResolutionTable({ resolutions }: { resolutions: MSourceResolution[] }) {
    if (resolutions.length === 0) return null;
    return (
        <div className={styles.resolutionSection}>
            <h4>M Expression / Source Resolutions ({resolutions.length})</h4>
            <table className={styles.table}>
                <thead>
                    <tr>
                        <th>Table</th>
                        <th>UC Reference</th>
                        <th>Status</th>
                        <th>Filter SQL</th>
                    </tr>
                </thead>
                <tbody>
                    {resolutions.map((r) => (
                        <tr key={r.table}>
                            <td>
                                {r.table}
                                {r.is_calculated && (
                                    <> <span className={`${styles.badge} ${styles.badgeCalc}`}>calculated</span></>
                                )}
                            </td>
                            <td>
                                {r.native_sql
                                    ? <code>NativeQuery SQL</code>
                                    : r.uc_ref
                                        ? <code>{r.uc_ref}</code>
                                        : <em style={{ color: "#aaa" }}>unresolved</em>
                                }
                            </td>
                            <td>
                                {r.is_calculated ? (
                                    <span className={`${styles.badge} ${styles.badgeCalc}`}>calculated</span>
                                ) : r.uc_ref || r.native_sql ? (
                                    <span className={`${styles.badge} ${styles.badgeResolved}`}>✓ resolved</span>
                                ) : (
                                    <span className={`${styles.badge} ${styles.badgeUnresolved}`}>✗ unresolved</span>
                                )}
                            </td>
                            <td>
                                {r.filter_sql
                                    ? <code style={{ fontSize: "0.75rem" }}>{r.filter_sql}</code>
                                    : <em style={{ color: "#aaa" }}>—</em>
                                }
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// ---------------------------------------------------------------------------
// ConvertPanel
// ---------------------------------------------------------------------------

export function ConvertPanel() {
    const [open, setOpen] = useState(false);
    const [file, setFile] = useState<File | null>(null);
    const [catalog, setCatalog] = useState("");
    const [schema, setSchema] = useState("");
    const [sourceCatalog, setSourceCatalog] = useState("");
    const [sourceSchema, setSourceSchema] = useState("");
    const [prefix, setPrefix] = useState("");
    const [factTables, setFactTables] = useState("");
    const [excludeTables, setExcludeTables] = useState("");
    const [includeIsolated, setIncludeIsolated] = useState(false);

    const { status, result, error, convert, reset } = useConvert();

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!file) return;
        convert({
            file,
            catalog,
            schema,
            source_catalog: sourceCatalog || undefined,
            source_schema: sourceSchema || undefined,
            prefix: prefix || undefined,
            fact_tables: factTables || undefined,
            exclude_tables: excludeTables || undefined,
            include_isolated: includeIsolated,
        });
    }

    return (
        <section className={styles.panel}>
            <button className={styles.toggle} onClick={() => setOpen((o) => !o)}>
                {open ? "▲ Convert PBIX" : "▼ Convert PowerBI PBIX to Metric Views"}
            </button>

            {open && (
                <>
                    <form className={styles.form} onSubmit={handleSubmit}>
                        <div>
                            <p className={styles.sectionLabel}>PBIX File</p>
                            <div className={styles.row}>
                                <label>
                                    File (.pbix)
                                    <input
                                        type="file"
                                        accept=".pbix"
                                        onChange={(e) => {
                                            setFile(e.target.files?.[0] ?? null);
                                            reset();
                                        }}
                                    />
                                </label>
                            </div>
                        </div>

                        <div>
                            <p className={styles.sectionLabel}>Destination</p>
                            <div className={styles.row}>
                                <label>
                                    Catalog <span className={styles.hint}>(required)</span>
                                    <input
                                        type="text"
                                        placeholder="prod"
                                        value={catalog}
                                        onChange={(e) => setCatalog(e.target.value)}
                                        required
                                    />
                                </label>
                                <label>
                                    Schema <span className={styles.hint}>(required)</span>
                                    <input
                                        type="text"
                                        placeholder="finance"
                                        value={schema}
                                        onChange={(e) => setSchema(e.target.value)}
                                        required
                                    />
                                </label>
                                <label>
                                    View name prefix
                                    <input
                                        type="text"
                                        placeholder=""
                                        value={prefix}
                                        onChange={(e) => setPrefix(e.target.value)}
                                    />
                                </label>
                            </div>
                        </div>

                        <div>
                            <p className={styles.sectionLabel}>Source Fallback</p>
                            <div className={styles.row}>
                                <label>
                                    Source catalog
                                    <input
                                        type="text"
                                        placeholder="hive_metastore"
                                        value={sourceCatalog}
                                        onChange={(e) => setSourceCatalog(e.target.value)}
                                    />
                                </label>
                                <label>
                                    Source schema
                                    <input
                                        type="text"
                                        placeholder="default"
                                        value={sourceSchema}
                                        onChange={(e) => setSourceSchema(e.target.value)}
                                    />
                                </label>
                            </div>
                        </div>

                        <div>
                            <p className={styles.sectionLabel}>Advanced</p>
                            <div className={styles.row}>
                                <label>
                                    Fact tables <span className={styles.hint}>(comma-separated)</span>
                                    <input
                                        type="text"
                                        placeholder="Sales, Orders"
                                        value={factTables}
                                        onChange={(e) => setFactTables(e.target.value)}
                                    />
                                </label>
                                <label>
                                    Exclude tables <span className={styles.hint}>(comma-separated)</span>
                                    <input
                                        type="text"
                                        placeholder="DateTable, Temp"
                                        value={excludeTables}
                                        onChange={(e) => setExcludeTables(e.target.value)}
                                    />
                                </label>
                                <label className={styles.checkLabel}>
                                    <input
                                        type="checkbox"
                                        checked={includeIsolated}
                                        onChange={(e) => setIncludeIsolated(e.target.checked)}
                                    />
                                    Include isolated tables
                                </label>
                            </div>
                        </div>

                        <div className={styles.actions}>
                            <button type="submit" disabled={!file || !catalog || !schema || status === "loading"}>
                                {status === "loading" ? "Converting…" : "Convert"}
                            </button>
                        </div>

                        {status === "error" && error && (
                            <p className={styles.error}>{error}</p>
                        )}
                    </form>

                    {status === "success" && result && (
                        <div className={styles.results}>
                            <div className={styles.summary}>
                                <div className={styles.stat}>
                                    <span className={styles.statValue}>{result.total_metric_views}</span>
                                    <span className={styles.statLabel}>Metric Views</span>
                                </div>
                                <div className={styles.stat}>
                                    <span className={styles.statValue}>{result.total_measures_converted}</span>
                                    <span className={styles.statLabel}>Measures Converted</span>
                                </div>
                                <div className={styles.stat}>
                                    <span className={styles.statValue}>{result.m_resolutions.length}</span>
                                    <span className={styles.statLabel}>Tables Resolved</span>
                                </div>
                            </div>

                            {result.warnings.length > 0 && (
                                <div className={styles.warnings}>
                                    <p className={styles.warningsTitle}>
                                        Warnings ({result.warnings.length})
                                    </p>
                                    <ul className={styles.warnList}>
                                        {result.warnings.map((w, i) => (
                                            <li key={i}>{w}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            <ResolutionTable resolutions={result.m_resolutions} />

                            {result.metric_views.length > 0 && (
                                <div>
                                    <p className={styles.sectionLabel}>
                                        Generated Metric Views
                                    </p>
                                    <div className={styles.metricViewList}>
                                        {result.metric_views.map((v) => (
                                            <MetricViewCard key={v.name} view={v} />
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}
        </section>
    );
}
