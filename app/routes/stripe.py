from pydantic import BaseModel

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.dependencies.auth import get_current_user
from app.services.stripe_service import (
    cancel_user_subscription,
    create_checkout_session,
    get_user_stripe_subscription_state,
    handle_stripe_webhook,
    reactivate_user_subscription,
    upgrade_user_subscription_to_pro_plus,
)


router = APIRouter(tags=["Stripe"])


class CheckoutRequest(BaseModel):
    plan: str


@router.post("/subscription/checkout")
async def create_subscription_checkout(
    payload: CheckoutRequest,
    current_user=Depends(get_current_user),
):
    email = getattr(current_user, "email", None)

    checkout_url = create_checkout_session(
        user_id=current_user.id,
        email=email,
        plan=payload.plan,
    )

    return {
        "url": checkout_url,
    }


@router.get("/subscription/manage")
async def get_subscription_manage(
    current_user=Depends(get_current_user),
):
    return get_user_stripe_subscription_state(
        user_id=current_user.id,
        email=getattr(current_user, "email", None),
    )


@router.post("/subscription/cancel")
async def cancel_subscription(
    current_user=Depends(get_current_user),
):
    return cancel_user_subscription(
        user_id=current_user.id,
        email=getattr(current_user, "email", None),
    )


@router.post("/subscription/reactivate")
async def reactivate_subscription(
    current_user=Depends(get_current_user),
):
    return reactivate_user_subscription(
        user_id=current_user.id,
        email=getattr(current_user, "email", None),
    )


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    current_user=Depends(get_current_user),
):
    return upgrade_user_subscription_to_pro_plus(
        user_id=current_user.id,
        email=getattr(current_user, "email", None),
    )


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get(
        "stripe-signature"
    )

    handle_stripe_webhook(
        payload=payload,
        signature=signature,
    )

    return JSONResponse(
        content={"received": True},
        status_code=200,
    )
