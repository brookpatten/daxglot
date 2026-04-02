export interface LineageColumn {
    table: string;
    column: string;
    type: string;
    upstream: LineageColumn[];
}

export interface WindowSpec {
    order: string;
    range: string;
    semiadditive?: string;
}

export interface Measure {
    id: string;
    metric_view: string;
    name: string;
    expr: string;
    comment?: string;
    display_name?: string;
    window: WindowSpec[];
    referenced_measures: string[];
    lineage: LineageColumn[];
}

export interface MeasureFilters {
    name?: string;
    metric_view?: string;
    catalog?: string;
    schema?: string;
    table?: string;
    column?: string;
    function?: string;
}

export interface CollectRequest {
    catalogs: string[];
    schema_?: string;
    view?: string;
    max_depth: number;
    no_lineage: boolean;
}

export interface CollectResult {
    measures_collected: number;
    files_written: string[];
}
