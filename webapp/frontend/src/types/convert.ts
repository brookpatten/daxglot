export interface MeasureConversion {
    name: string;
    dax: string;
    sql: string;
    warnings: string[];
    window?: Array<{ order: string; range: string; semiadditive?: string }>;
    is_approximate: boolean;
}

export interface MSourceResolution {
    table: string;
    uc_ref?: string;
    filter_sql?: string;
    native_sql?: string;
    is_calculated: boolean;
}

export interface MetricView {
    name: string;
    source_table: string;
    source_uc_ref?: string;
    dimensions_count: number;
    joins_count: number;
    measures: MeasureConversion[];
    yaml_content: string;
    sql_ddl: string;
}

export interface ConvertResult {
    catalog: string;
    schema_: string;
    metric_views: MetricView[];
    warnings: string[];
    m_resolutions: MSourceResolution[];
    total_metric_views: number;
    total_measures_converted: number;
}

export interface ConvertRequest {
    file: File;
    catalog: string;
    schema: string;
    source_catalog?: string;
    source_schema?: string;
    prefix?: string;
    fact_tables?: string;
    exclude_tables?: string;
    include_isolated?: boolean;
    dialect?: string;
}
