from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, field_validator


class LineageColumnOut(BaseModel):
    table: str
    column: str
    type: str
    upstream: list["LineageColumnOut"] = []


LineageColumnOut.model_rebuild()


class WindowSpecOut(BaseModel):
    order: str
    range: str
    semiadditive: Optional[str] = None


class MeasureOut(BaseModel):
    id: str  # filename stem, e.g. "prod.finance.sales_metrics.total_revenue"
    metric_view: str
    name: str
    expr: str
    comment: Optional[str] = None
    display_name: Optional[str] = None
    window: list[WindowSpecOut] = []
    referenced_measures: list[str] = []
    lineage: list[LineageColumnOut] = []


class CollectRequest(BaseModel):
    catalogs: list[str] = []
    schema_: Optional[str] = None
    view: Optional[str] = None
    max_depth: int = 100
    no_lineage: bool = False

    model_config = {"populate_by_name": True}


class CollectOut(BaseModel):
    measures_collected: int
    files_written: list[str]


# ---------------------------------------------------------------------------
# PBIX conversion models
# ---------------------------------------------------------------------------


class MeasureConversionOut(BaseModel):
    name: str
    dax: str
    sql: str
    warnings: list[str] = []
    window: Optional[list[dict]] = None
    is_approximate: bool = False


class MSourceResolutionOut(BaseModel):
    table: str
    uc_ref: Optional[str] = None
    filter_sql: Optional[str] = None
    native_sql: Optional[str] = None
    is_calculated: bool = False


class MetricViewOut(BaseModel):
    name: str
    source_table: str
    source_uc_ref: Optional[str] = None
    dimensions_count: int
    joins_count: int
    measures: list[MeasureConversionOut] = []
    yaml_content: str
    sql_ddl: str


class ConvertOut(BaseModel):
    catalog: str
    schema_: str
    metric_views: list[MetricViewOut] = []
    warnings: list[str] = []
    m_resolutions: list[MSourceResolutionOut] = []
    total_metric_views: int
    total_measures_converted: int


# ---------------------------------------------------------------------------
# Measure comparison models
# ---------------------------------------------------------------------------


class LeafSourceOut(BaseModel):
    table: str
    column: str


class ExprComparisonOut(BaseModel):
    raw_a: str
    raw_b: str
    normalized_a: str
    normalized_b: str
    same: bool


class WindowFieldDiffOut(BaseModel):
    spec_index: int
    field: str
    value_a: Optional[str]
    value_b: Optional[str]


class WindowComparisonOut(BaseModel):
    specs_a: list[WindowSpecOut]
    specs_b: list[WindowSpecOut]
    same: bool
    field_diffs: list[WindowFieldDiffOut] = []


class LineageComparisonOut(BaseModel):
    leaf_sources_a: list[LeafSourceOut]
    leaf_sources_b: list[LeafSourceOut]
    shared_leaves: list[LeafSourceOut]
    only_in_a: list[LeafSourceOut]
    only_in_b: list[LeafSourceOut]
    leaves_same: bool
    has_extra_hops_a: bool
    has_extra_hops_b: bool


class PairComparisonOut(BaseModel):
    id_a: str
    id_b: str
    view_a: str
    view_b: str
    name_a: str
    name_b: str
    score: float
    label: str
    expr: ExprComparisonOut
    window: WindowComparisonOut
    lineage: LineageComparisonOut


class CompareRequest(BaseModel):
    ids: list[str]

    @field_validator("ids")
    @classmethod
    def exactly_two(cls, v: list[str]) -> list[str]:
        if len(v) != 2:
            raise ValueError(
                "Exactly 2 measure ids are required for comparison.")
        return v


class CompareOut(BaseModel):
    measures: list[MeasureOut]
    pairs: list[PairComparisonOut]


# ---------------------------------------------------------------------------
# Similarity search models
# ---------------------------------------------------------------------------


class SimilarMeasureOut(BaseModel):
    score: float
    label: str
    measure: MeasureOut
