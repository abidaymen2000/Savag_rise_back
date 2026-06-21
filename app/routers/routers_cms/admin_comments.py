from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.review import AdminReviewUpdate, PaginatedReviewsOut, ReviewOut, ReviewStatus
from app.schemas.vlog import PaginatedVlogCommentsOut, VlogCommentOut, VlogCommentStatus, VlogCommentUpdate
from app.services.services_cms import engagement_service


router = APIRouter(prefix="/admin/comments", tags=["admin-comments"])


@router.get("", response_model=PaginatedVlogCommentsOut)
async def admin_list_comments(
    _admin=Depends(require_permission("engagement")),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: Optional[VlogCommentStatus] = Query(None, alias="status"),
    episode_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Recherche dans le contenu du commentaire"),
):
    return await engagement_service.list_comments(db, page, page_size, status_filter, episode_id, user_id, q)


@router.get("/product-reviews", response_model=PaginatedReviewsOut)
async def admin_list_product_reviews(
    _admin=Depends(require_permission("engagement")),
    db=Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: Optional[ReviewStatus] = Query(None, alias="status"),
    product_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    rating: Optional[int] = Query(None, ge=1, le=5),
    q: Optional[str] = Query(None, description="Recherche dans le titre ou commentaire"),
):
    return await engagement_service.list_product_reviews(db, page, page_size, status_filter, product_id, user_id, rating, q)


@router.patch("/product-reviews/{review_id}", response_model=ReviewOut)
async def admin_update_product_review(
    review_id: str,
    payload: AdminReviewUpdate,
    _admin=Depends(require_permission("engagement")),
    db=Depends(get_db),
):
    return await engagement_service.update_product_review(db, review_id, payload)


@router.delete("/product-reviews/{review_id}", status_code=204)
async def admin_delete_product_review(
    review_id: str,
    _admin=Depends(require_permission("engagement")),
    db=Depends(get_db),
):
    await engagement_service.delete_product_review(db, review_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{comment_id}", response_model=VlogCommentOut)
async def admin_update_comment(
    comment_id: str,
    payload: VlogCommentUpdate,
    _admin=Depends(require_permission("engagement")),
    db=Depends(get_db),
):
    return await engagement_service.update_comment(db, comment_id, payload)


@router.delete("/{comment_id}", status_code=204)
async def admin_delete_comment(
    comment_id: str,
    _admin=Depends(require_permission("engagement")),
    db=Depends(get_db),
):
    await engagement_service.delete_comment(db, comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
