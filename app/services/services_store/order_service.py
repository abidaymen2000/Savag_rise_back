from app.services.services_store import order_domain_service


async def quote_order(db, order_in, request, current_user):
    return await order_domain_service.quote_order(db, order_in, current_user)


async def create_order(db, order_in, background_tasks, request, current_user, idempotency_key: str):
    return await order_domain_service.create_order(
        db,
        order_in,
        background_tasks,
        request,
        current_user,
        idempotency_key=idempotency_key,
    )


async def cancel_order(db, order_id: str, background_tasks, current_user, reason: str | None = None):
    return await order_domain_service.cancel_order(
        db,
        order_id,
        actor_type="customer",
        actor_id=str(current_user["_id"]),
        current_user_id=str(current_user["_id"]),
        reason=reason,
    )
