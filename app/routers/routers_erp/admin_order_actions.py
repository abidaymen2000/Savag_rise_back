from fastapi import APIRouter, Depends, Path, Query, Request

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.order import OrderOut
from app.schemas.order_admin import OrderAssignIn, OrderNoteIn, OrderNoteOut, OrderTagsIn, OrderTimelineEventOut
from app.services.services_erp import admin_order_service, order_advanced_service


router = APIRouter(prefix="/orders", tags=["admin-order-actions"])


@router.get("/{order_id}", response_model=OrderOut, summary="Lire une commande par son ID")
async def api_get_order(
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    _admin=Depends(require_permission("orders")),
):
    return await admin_order_service.get_order(db, order_id)


@router.patch("/{order_id}/status", summary="Mettre a jour le statut d'une commande")
async def api_update_status(
    order_id: str = Path(..., description="ID de la commande"),
    new_status: str = Query(..., description="Nouveau statut"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await order_advanced_service.update_status_advanced(db, order_id, new_status, current_admin)


@router.patch("/{order_id}/pay", summary="Marquer la commande comme payee")
async def api_mark_paid(
    request: Request,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    _admin=Depends(require_permission("orders")),
):
    return await admin_order_service.mark_paid(db, order_id, request)


@router.post("/{order_id}/notes", response_model=OrderNoteOut, status_code=201)
async def api_add_order_note(
    payload: OrderNoteIn,
    order_id: str = Path(...),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await order_advanced_service.add_note(db, order_id, payload, current_admin)


@router.patch("/{order_id}/tags")
async def api_set_order_tags(
    payload: OrderTagsIn,
    order_id: str = Path(...),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await order_advanced_service.set_tags(db, order_id, payload, current_admin)


@router.patch("/{order_id}/assign")
async def api_assign_order(
    payload: OrderAssignIn,
    order_id: str = Path(...),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await order_advanced_service.assign_order(db, order_id, payload, current_admin)


@router.get("/{order_id}/timeline", response_model=list[OrderTimelineEventOut])
async def api_order_timeline(
    order_id: str = Path(...),
    db=Depends(get_db),
    _admin=Depends(require_permission("orders")),
):
    return await order_advanced_service.list_timeline(db, order_id)
