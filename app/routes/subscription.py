from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth import get_current_user
from app.services.db_service import (
    check_document_upload_quota,
    FREE_DOCUMENT_LIMIT,
    PRO_MONTHLY_DOCUMENT_LIMIT,
    supabase,
)


router = APIRouter(
    prefix="/subscription",
    tags=["Subscription"],
)


@router.get("")
async def get_subscription(
    current_user=Depends(get_current_user),
):
    """
    Return the authenticated user's current subscription
    and document usage.

    The authenticated backend user is the only source
    of the user_id.
    """

    user_id = current_user.id

    # -------------------------------------------------
    # GET SUBSCRIPTION
    # -------------------------------------------------

    response = (
        supabase
        .table("subscriptions")
        .select(
            """
            plan,
            status,
            current_period_start,
            current_period_end
            """
        )
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )

    subscription_data = (
        response.data or []
    )

    # -------------------------------------------------
    # SAFETY
    # -------------------------------------------------

    if not subscription_data:

        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    subscription = subscription_data[0]

    plan = (
        subscription.get("plan")
        or "free"
    )

    status = (
        subscription.get("status")
        or "active"
    )

    # -------------------------------------------------
    # USE THE SAME QUOTA LOGIC AS UPLOAD
    # -------------------------------------------------

    quota = check_document_upload_quota(
        user_id
    )

    # -------------------------------------------------
    # LIMIT
    # -------------------------------------------------

    if plan == "free":

        documents_limit = (
            FREE_DOCUMENT_LIMIT
        )

    elif plan == "pro":

        documents_limit = (
            PRO_MONTHLY_DOCUMENT_LIMIT
        )

    else:

        documents_limit = (
            quota.get("limit", 0)
        )

    # -------------------------------------------------
    # RESPONSE
    # -------------------------------------------------

    return {
        "plan": plan,
        "status": status,

        "documents_used": (
            quota.get("used", 0)
        ),

        "documents_limit": (
            documents_limit
        ),

        "remaining": (
            quota.get("remaining", 0)
        ),

        "current_period_start": (
            subscription.get(
                "current_period_start"
            )
        ),

        "current_period_end": (
            subscription.get(
                "current_period_end"
            )
        ),
    }