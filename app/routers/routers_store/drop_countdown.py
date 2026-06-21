from fastapi import APIRouter, Depends, Request

from app.db import get_db
from app.dependencies import get_current_user
from app.schemas.drop_countdown import DropCountdownOut, DropNotificationStatus
from app.services.services_store import drop_countdown_service


router = APIRouter(tags=["drop-countdown"])


@router.get("/storefront/drop-countdown", response_model=DropCountdownOut)
async def read_storefront_drop_countdown(db=Depends(get_db)):
    return await drop_countdown_service.get_active_storefront_drop(db)


@router.get("/storefront/drop-countdown/notification-status", response_model=DropNotificationStatus)
async def read_drop_notification_status(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await drop_countdown_service.get_notification_status(db, current_user)


@router.post("/storefront/drop-countdown/notify-me", response_model=DropNotificationStatus, status_code=201)
async def subscribe_drop_notification(
    request: Request,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await drop_countdown_service.subscribe_notification(db, request, current_user)


@router.delete("/storefront/drop-countdown/notify-me", response_model=DropNotificationStatus)
async def unsubscribe_drop_notification(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    return await drop_countdown_service.unsubscribe_notification(db, current_user)
