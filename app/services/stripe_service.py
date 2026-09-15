import os
from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import HTTPException

from app.services.db_service import supabase


STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "").strip()
STRIPE_PRICE_PRO_PLUS = os.getenv("STRIPE_PRICE_PRO_PLUS", "").strip()
FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000",
).rstrip("/")

if STRIPE_SECRET_KEY:
    stripe_client = stripe.StripeClient(STRIPE_SECRET_KEY)
else:
    stripe_client = None


def _require_stripe() -> stripe.StripeClient:
    if stripe_client is None:
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured on the server.",
        )

    return stripe_client


def _price_id_for_plan(plan: str) -> str:
    if plan == "pro":
        price_id = STRIPE_PRICE_PRO
    elif plan == "pro_plus":
        price_id = STRIPE_PRICE_PRO_PLUS
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid paid subscription plan.",
        )

    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Stripe price is not configured for plan '{plan}'.",
        )

    return price_id


def _normalize_timestamp(value: Any) -> str | None:
    if value is None:
        return None

    try:
        timestamp = int(value)
        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _get_plan_from_price_id(price_id: str | None) -> str | None:
    if not price_id:
        return None

    if price_id == STRIPE_PRICE_PRO:
        return "pro"

    if price_id == STRIPE_PRICE_PRO_PLUS:
        return "pro_plus"

    return None


def _subscription_plan(subscription: Any) -> str | None:
    metadata = getattr(subscription, "metadata", None)

    if metadata:
        plan = metadata.get("plan")
        if plan in {"pro", "pro_plus"}:
            return plan

    items = getattr(subscription, "items", None)
    data = getattr(items, "data", None) or []

    for item in data:
        price = getattr(item, "price", None)
        price_id = getattr(price, "id", None)

        plan = _get_plan_from_price_id(price_id)
        if plan:
            return plan

    return None


def _subscription_user_id(subscription: Any) -> str | None:
    metadata = getattr(subscription, "metadata", None)

    if not metadata:
        return None

    user_id = metadata.get("user_id")

    if not user_id:
        return None

    return str(user_id)


def _upsert_subscription_from_stripe(
    subscription: Any,
    fallback_user_id: str | None = None,
) -> None:
    plan = _subscription_plan(subscription)
    user_id = _subscription_user_id(subscription) or fallback_user_id

    if plan not in {"pro", "pro_plus"}:
        raise ValueError("Unsupported Stripe subscription plan.")

    if not user_id:
        raise ValueError(
            "Stripe subscription is missing the Life AiOS user_id."
        )

    status = (
        getattr(subscription, "status", None)
        or "inactive"
    )

    current_period_start = _normalize_timestamp(
        getattr(subscription, "current_period_start", None)
    )

    current_period_end = _normalize_timestamp(
        getattr(subscription, "current_period_end", None)
    )

    payload = {
        "user_id": user_id,
        "plan": plan,
        "status": status,
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
    }

    existing = (
        supabase
        .table("subscriptions")
        .select("user_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        (
            supabase
            .table("subscriptions")
            .update(
                {
                    "plan": payload["plan"],
                    "status": payload["status"],
                    "current_period_start": payload[
                        "current_period_start"
                    ],
                    "current_period_end": payload[
                        "current_period_end"
                    ],
                }
            )
            .eq("user_id", user_id)
            .execute()
        )
    else:
        (
            supabase
            .table("subscriptions")
            .insert(payload)
            .execute()
        )


def create_checkout_session(
    *,
    user_id: str,
    email: str | None,
    plan: str,
) -> str:
    client = _require_stripe()
    price_id = _price_id_for_plan(plan)

    metadata = {
        "user_id": str(user_id),
        "plan": plan,
    }

    try:
        session = client.v1.checkout.sessions.create(
            params={
                "mode": "subscription",
                "line_items": [
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                "success_url": (
                    f"{FRONTEND_URL}/settings"
                    "?stripe=success"
                ),
                "cancel_url": (
                    f"{FRONTEND_URL}/settings"
                    "?stripe=cancelled"
                ),
                "customer_email": email or None,
                "client_reference_id": str(user_id),
                "metadata": metadata,
                "subscription_data": {
                    "metadata": metadata,
                },
                "allow_promotion_codes": True,
            },
        )
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to start Stripe Checkout.",
        ) from exc

    checkout_url = getattr(session, "url", None)

    if not checkout_url:
        raise HTTPException(
            status_code=502,
            detail="Stripe did not return a Checkout URL.",
        )

    return checkout_url


def handle_stripe_webhook(
    *,
    payload: bytes,
    signature: str | None,
) -> None:
    webhook_secret = os.getenv(
        "STRIPE_WEBHOOK_SECRET",
        "",
    ).strip()

    if not webhook_secret:
        raise HTTPException(
            status_code=503,
            detail="Stripe webhook secret is not configured.",
        )

    if not signature:
        raise HTTPException(
            status_code=400,
            detail="Missing Stripe signature.",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            webhook_secret,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook payload.",
        ) from exc
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid Stripe webhook signature.",
        ) from exc

    event_type = event.get("type")
    data_object = (
        event.get("data", {})
        .get("object")
    ) or {}

    if event_type == "checkout.session.completed":
        session_mode = data_object.get("mode")

        if session_mode != "subscription":
            return

        subscription_id = data_object.get(
            "subscription"
        )

        fallback_user_id = (
            data_object
            .get("metadata", {})
            .get("user_id")
        )

        if not subscription_id:
            return

        client = _require_stripe()

        try:
            subscription = (
                client.v1.subscriptions.retrieve(
                    subscription_id
                )
            )

            _upsert_subscription_from_stripe(
                subscription,
                fallback_user_id=fallback_user_id,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc
        except stripe.StripeError as exc:
            raise HTTPException(
                status_code=502,
                detail="Unable to retrieve Stripe subscription.",
            ) from exc

        return

    if event_type in {
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        plan = _subscription_plan_from_event_object(
            data_object
        )
        user_id = _user_id_from_event_object(
            data_object
        )

        if not user_id or plan not in {
            "pro",
            "pro_plus",
        }:
            return

        status = (
            data_object.get("status")
            or (
                "canceled"
                if event_type
                == "customer.subscription.deleted"
                else "inactive"
            )
        )

        payload_update = {
            "plan": plan,
            "status": status,
            "current_period_start": _normalize_timestamp(
                data_object.get(
                    "current_period_start"
                )
            ),
            "current_period_end": _normalize_timestamp(
                data_object.get(
                    "current_period_end"
                )
            ),
        }

        (
            supabase
            .table("subscriptions")
            .update(payload_update)
            .eq("user_id", user_id)
            .execute()
        )

        return

    if event_type == "invoice.payment_failed":
        subscription_id = data_object.get(
            "subscription"
        )

        if not subscription_id:
            return

        client = _require_stripe()

        try:
            subscription = (
                client.v1.subscriptions.retrieve(
                    subscription_id
                )
            )
        except stripe.StripeError as exc:
            raise HTTPException(
                status_code=502,
                detail="Unable to retrieve Stripe subscription.",
            ) from exc

        user_id = _subscription_user_id(subscription)

        if user_id:
            (
                supabase
                .table("subscriptions")
                .update(
                    {"status": "past_due"}
                )
                .eq("user_id", user_id)
                .execute()
            )


def _subscription_plan_from_event_object(
    subscription: dict[str, Any],
) -> str | None:
    metadata = subscription.get("metadata") or {}

    plan = metadata.get("plan")

    if plan in {"pro", "pro_plus"}:
        return plan

    items = subscription.get("items") or {}
    data = items.get("data") or []

    for item in data:
        price = item.get("price") or {}
        price_id = price.get("id")

        plan = _get_plan_from_price_id(price_id)

        if plan:
            return plan

    return None


def _user_id_from_event_object(
    subscription: dict[str, Any],
) -> str | None:
    metadata = subscription.get("metadata") or {}
    user_id = metadata.get("user_id")

    return str(user_id) if user_id else None
