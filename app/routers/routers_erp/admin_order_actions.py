from fastapi import APIRouter, Depends, Path, Request

from app.db import get_db
from app.dependencies_admin import require_permission
from app.schemas.order import OrderActionReasonIn, OrderOut, OrderRefundIn
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


@router.post("/{order_id}/confirm", summary="Confirmer une commande")
async def api_confirm_order(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.confirm_order(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/prepare", summary="Passer une commande en preparation")
async def api_prepare_order(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.prepare_order(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/ship", summary="Expedier une commande")
async def api_ship_order(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.ship_order(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/deliver", summary="Marquer une commande comme livree")
async def api_deliver_order(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.deliver_order(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/cancel", summary="Annuler une commande")
async def api_cancel_order(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.cancel_order(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/mark-paid", summary="Marquer la commande comme payee")
async def api_mark_paid(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.mark_paid(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/request-return", summary="Demander un retour")
async def api_request_return(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.request_return(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/return-in-transit", summary="Retour en transit")
async def api_return_in_transit(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.mark_return_in_transit(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/receive-return", summary="Retour recu")
async def api_receive_return(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.receive_return(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/restock-return", summary="Remettre en stock un retour revendable")
async def api_restock_return(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.restock_returned_items(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/mark-return-damaged", summary="Marquer un retour comme non revendable")
async def api_mark_return_damaged(
    payload: OrderActionReasonIn | None,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.mark_return_damaged(db, order_id, current_admin, getattr(payload, "reason", None))


@router.post("/{order_id}/refund", summary="Rembourser une commande")
async def api_refund_order(
    payload: OrderRefundIn,
    order_id: str = Path(..., description="ID de la commande"),
    db=Depends(get_db),
    current_admin=Depends(require_permission("orders")),
):
    return await admin_order_service.refund_order(db, order_id, current_admin, payload.amount, payload.reason)


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
