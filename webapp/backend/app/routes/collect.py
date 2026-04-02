from fastapi import APIRouter

from ..models import CollectOut, CollectRequest
from ..services import collector

router = APIRouter(prefix="/api/collect", tags=["collect"])


@router.post("", response_model=CollectOut)
def collect_measures(request: CollectRequest) -> CollectOut:
    """Trigger live collection from Databricks. Synchronous — may take several minutes."""
    return collector.run_collect(
        catalogs=request.catalogs,
        schema=request.schema_,
        view=request.view,
        max_depth=request.max_depth,
        no_lineage=request.no_lineage,
    )
