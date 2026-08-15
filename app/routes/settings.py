from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import BaseModel

from app.dependencies.auth import (
    get_current_user,
)

from app.services.db_service import (
    get_notification_preferences,
    save_notification_preferences,
    delete_account_data,
    verify_account_data_deleted,
    supabase,
    export_account_data,
)


router = APIRouter()


# =========================================================
# REQUEST MODELS
# =========================================================

class NotificationRequest(BaseModel):
    enabled: bool
    morning_time: str
    evening_time: str
    daily_briefing: bool
    evening_review: bool
    deadline_reminders: bool


# =========================================================
# NOTIFICATION SETTINGS
# =========================================================

@router.get("/notification-settings")
async def notification_settings(
    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user.id

    return get_notification_preferences(
        user_id
    )


@router.post("/notification-settings")
async def save_settings(
    request: NotificationRequest,
    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user.id

    return save_notification_preferences(
        user_id,
        request.enabled,
        request.morning_time,
        request.evening_time,
        request.daily_briefing,
        request.evening_review,
        request.deadline_reminders,
    )


# =========================================================
# DELETE ACCOUNT
# =========================================================

@router.delete("/account")
async def delete_account(
    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user.id

    try:

        # -------------------------------------------------
        # DELETE ALL APPLICATION DATA
        # -------------------------------------------------

        delete_account_data(
            user_id
        )

        # -------------------------------------------------
        # VERIFY APPLICATION DATA DELETION
        # -------------------------------------------------

        verified = (
            verify_account_data_deleted(
                user_id
            )
        )

        if not verified:

            raise HTTPException(
                status_code=500,
                detail=(
                    "Account data could not be "
                    "completely deleted"
                ),
            )

        # -------------------------------------------------
        # DELETE SUPABASE AUTH USER
        # -------------------------------------------------

        supabase.auth.admin.delete_user(
            user_id
        )

        return {
            "success": True,
            "message": "Account deleted successfully",
        }

    except HTTPException:
        raise

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Failed to delete account",
        )


# =========================================================
# DATA EXPORT
# =========================================================

@router.get("/account/export")
async def export_account(
    current_user=Depends(
        get_current_user
    ),
):
    """
    Export all application data
    belonging to the authenticated user.

    IMPORTANT:
    The user_id comes exclusively
    from the authenticated session.
    """

    user_id = current_user.id

    try:

        export_data = (
            export_account_data(
                user_id
            )
        )

        return {
            "success": True,
            "data": export_data,
        }

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Failed to export account data",
        )