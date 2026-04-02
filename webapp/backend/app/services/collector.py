"""Collect metric view definitions from Databricks into MEASURES_DIR.

Requires databricks-connect and a configured Databricks workspace.
Raises HTTPException 503 if databricks-connect is unavailable or not configured.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from ..config import settings
from ..models import CollectOut

logger = logging.getLogger(__name__)


def run_collect(
    catalogs: list[str],
    schema: Optional[str],
    view: Optional[str],
    max_depth: int,
    no_lineage: bool,
) -> CollectOut:
    """Run measurediff collection synchronously and return the result.

    Raises:
        HTTPException 503: If databricks-connect is not installed or not configured.
        HTTPException 500: If collection fails for any other reason.
    """
    try:
        from databricks.connect import DatabricksSession
        from measurediff.collector import MetricViewCollector
        from measurediff.lineage import LineageCollector
        from measurediff import serializer
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"databricks-connect is not installed: {exc}",
        ) from exc

    try:
        spark = DatabricksSession.builder.getOrCreate()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Databricks — check DATABRICKS_HOST / DATABRICKS_TOKEN: {exc}",
        ) from exc

    try:
        collector = MetricViewCollector(spark)
        catalog_list: list[Optional[str]] = list(
            catalogs) if catalogs else [None]

        all_defs = []
        for cat in catalog_list:
            all_defs.extend(collector.collect(
                catalog=cat, schema=schema, view=view))

        if not all_defs:
            return CollectOut(measures_collected=0, files_written=[])

        effective_depth = 0 if no_lineage else max_depth
        if effective_depth > 0:
            lc = LineageCollector(spark, max_depth=effective_depth)
            all_defs = [lc.enrich(d) for d in all_defs]

        out_path = settings.measures_dir_resolved
        written: list[Path] = []
        for view_def in all_defs:
            written.extend(serializer.write_measures(view_def, out_path))

        return CollectOut(
            measures_collected=len(written),
            files_written=[str(p) for p in written],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Collection failed")
        raise HTTPException(
            status_code=500, detail=f"Collection failed: {exc}") from exc
