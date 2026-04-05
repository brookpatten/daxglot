from typing import Optional

from fastapi import APIRouter, HTTPException

from ..models import MeasureOut
from ..services import measure_store

router = APIRouter(prefix="/api/measures", tags=["measures"])


@router.get("", response_model=list[MeasureOut])
def list_measures(
    name: Optional[str] = None,
    display_name: Optional[str] = None,
    metric_view: Optional[str] = None,
    catalog: Optional[str] = None,
    schema: Optional[str] = None,
    table: Optional[str] = None,
    column: Optional[str] = None,
    function: Optional[str] = None,
) -> list[MeasureOut]:
    """List measures, optionally filtered. All parameters are case-insensitive substrings."""
    return measure_store.search(
        name=name,
        display_name=display_name,
        metric_view=metric_view,
        catalog=catalog,
        schema=schema,
        table=table,
        column=column,
        function=function,
    )


@router.get("/{measure_id:path}", response_model=MeasureOut)
def get_measure(measure_id: str) -> MeasureOut:
    """Get a single measure by its ID (filename stem)."""
    measure = measure_store.get_by_id(measure_id)
    if measure is None:
        raise HTTPException(
            status_code=404, detail=f"Measure '{measure_id}' not found")
    return measure
