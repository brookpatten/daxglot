"""Route for uploading and converting a PowerBI PBIX file."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Form, UploadFile

from ..models import ConvertOut
from ..services import converter

router = APIRouter(prefix="/api/convert", tags=["convert"])


@router.post("", response_model=ConvertOut)
async def convert_pbix(
    file: UploadFile,
    catalog: str = Form(...),
    schema: str = Form(...),
    source_catalog: Optional[str] = Form(default=None),
    source_schema: Optional[str] = Form(default=None),
    prefix: str = Form(default=""),
    fact_tables: Optional[str] = Form(default=None),
    exclude_tables: Optional[str] = Form(default=None),
    include_isolated: bool = Form(default=False),
    dialect: str = Form(default="databricks"),
) -> ConvertOut:
    """Upload a .pbix file and convert it to Databricks metric views.

    Returns structured output describing each generated metric view, the DAX → SQL
    translations performed, M-expression resolutions, and any warnings.
    """
    pbix_bytes = await file.read()
    filename = file.filename or "upload.pbix"

    return converter.run_convert(
        pbix_bytes=pbix_bytes,
        pbix_filename=filename,
        catalog=catalog,
        schema=schema,
        source_catalog=source_catalog or None,
        source_schema=source_schema or None,
        fact_tables=fact_tables or None,
        prefix=prefix,
        exclude_tables=exclude_tables or None,
        include_isolated=include_isolated,
        dialect=dialect,
    )
