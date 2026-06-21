from fastapi import APIRouter, Depends, Query, Response

from app.db import get_db
from app.services.services_store import meta_catalog_service


router = APIRouter(prefix="/meta", tags=["meta-catalog"])


@router.get("/catalog.csv", summary="Flux CSV catalogue Meta")
async def meta_catalog_csv(
    include_out_of_stock: bool = Query(True, description="Inclure les articles hors stock dans le feed Meta"),
    include_missing_images: bool = Query(False, description="Inclure les lignes sans image_link"),
    db=Depends(get_db),
) -> Response:
    return await meta_catalog_service.build_meta_catalog_csv(db, include_out_of_stock, include_missing_images)
