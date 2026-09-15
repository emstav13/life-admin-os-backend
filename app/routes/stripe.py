from pydantic import BaseModel

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.dependencies.auth import get_current_user
from app.services.stripe_service import (
    create_checkout_session,
    handle_stripe_webhook,
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
