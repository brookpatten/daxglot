"""Run pbi2dbr pipeline: extract PBIX → analyse model → generate metric views."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from ..models import (
    ConvertOut,
    MeasureConversionOut,
    MetricViewOut,
    MSourceResolutionOut,
)


def run_convert(
    pbix_bytes: bytes,
    pbix_filename: str,
    catalog: str,
    schema: str,
    source_catalog: Optional[str] = None,
    source_schema: Optional[str] = None,
    fact_tables: Optional[str] = None,
    prefix: str = "",
    exclude_tables: Optional[str] = None,
    include_isolated: bool = False,
    dialect: str = "databricks",
) -> ConvertOut:
    """Execute pbi2dbr pipeline on an uploaded PBIX file.

    The file is written to a temporary directory, processed, then cleaned up.

    Raises:
        HTTPException 400: If extraction or analysis fails (bad file, etc.).
        HTTPException 500: For unexpected internal errors.
    """
    try:
        from pbi2dbr.analyzer import AnalysisOptions, ModelAnalyzer
        from pbi2dbr.extractor import PbixExtractor
        from pbi2dbr.generator import MetricViewGenerator
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"pbi2dbr is not installed: {exc}",
        ) from exc

    # Write uploaded bytes to a temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        pbix_path = Path(tmpdir) / pbix_filename
        pbix_path.write_bytes(pbix_bytes)

        # --- Extract ---
        try:
            extractor = PbixExtractor(pbix_path)
            model = extractor.extract(
                source_catalog=source_catalog,
                source_schema=source_schema,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract PBIX: {exc}",
            ) from exc

        # --- Build M-source resolution summary ---
        m_resolutions: list[MSourceResolutionOut] = [
            MSourceResolutionOut(
                table=st.name,
                uc_ref=st.uc_ref,
                filter_sql=st.filter_expr,
                native_sql=st.source_sql,
                is_calculated=st.is_calculated,
            )
            for st in model.source_tables.values()
        ]

        # --- Analyse ---
        fact_list = (
            [t.strip() for t in fact_tables.split(",")] if fact_tables else None
        )
        excl_list = (
            [t.strip() for t in exclude_tables.split(",")] if exclude_tables else []
        )

        opts = AnalysisOptions(
            fact_tables=fact_list,
            include_isolated=include_isolated,
            exclude_tables=excl_list,
        )

        analyzer = ModelAnalyzer(model, opts)
        facts = analyzer.analyze()
        all_warnings: list[str] = list(analyzer.warnings)

        if not facts:
            return ConvertOut(
                catalog=catalog,
                schema_=schema,
                metric_views=[],
                warnings=all_warnings
                + ["No fact tables found — use fact_tables to specify them manually."],
                m_resolutions=m_resolutions,
                total_metric_views=0,
                total_measures_converted=0,
            )

        # --- Generate metric views ---
        gen = MetricViewGenerator(dialect=dialect)
        metric_views: list[MetricViewOut] = []
        total_measures = 0

        for fact in facts:
            spec = gen.build_spec(
                fact,
                target_catalog=catalog,
                target_schema=schema,
                view_name_prefix=prefix,
            )

            yaml_content = gen.to_yaml(spec)
            sql_ddl = gen.to_sql_ddl(spec, catalog=catalog, schema=schema)

            converted: list[MeasureConversionOut] = []
            for m in spec.measures:
                window = None
                if m.window:
                    window = [
                        {
                            "order": w.get("order", ""),
                            "range": w.get("range", ""),
                            **(
                                {"semiadditive": w["semiadditive"]}
                                if w.get("semiadditive")
                                else {}
                            ),
                        }
                        for w in (
                            m.window
                            if isinstance(m.window, list)
                            else [m.window]
                        )
                    ]
                converted.append(
                    MeasureConversionOut(
                        name=m.name,
                        dax=m.original_dax or "",
                        sql=m.expr or "",
                        warnings=list(m.warnings),
                        window=window,
                        is_approximate=m.is_approximate,
                    )
                )
                all_warnings.extend(
                    f"[{spec.name}.{m.name}] {w}" for w in m.warnings
                )

            total_measures += len(converted)

            metric_views.append(
                MetricViewOut(
                    name=spec.name,
                    source_table=fact.name,
                    source_uc_ref=fact.source_table.uc_ref,
                    dimensions_count=len(spec.dimensions),
                    joins_count=len(spec.joins),
                    measures=converted,
                    yaml_content=yaml_content,
                    sql_ddl=sql_ddl,
                )
            )

        return ConvertOut(
            catalog=catalog,
            schema_=schema,
            metric_views=metric_views,
            warnings=all_warnings,
            m_resolutions=m_resolutions,
            total_metric_views=len(metric_views),
            total_measures_converted=total_measures,
        )
