from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.dependencies.auth import (
    get_current_user,
)

from app.services.db_service import (
    get_reminders,
    mark_reminder_as_shown,
)


router = APIRouter()


# =========================================================
# GET USER REMINDERS
# =========================================================

@router.get("/reminders")
async def reminders(
    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user.id

    try:

        return get_reminders(
            user_id
        )

    except Exception as error:

        print(
            "Failed to load reminders:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load reminders",
        )


# =========================================================
# MARK REMINDER AS SHOWN
# =========================================================

@router.patch(
    "/reminders/{reminder_id}/shown"
)
async def mark_reminder_shown(
    reminder_id: str,

    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user.id

    try:

        # -------------------------------------------------
        # SECURITY CHECK
        # Make sure the reminder belongs to this user.
        # -------------------------------------------------

        reminders = get_reminders(
            user_id
        )

        reminder_exists = any(
            reminder.get("id")
            == reminder_id
            for reminder in reminders
        )

        if not reminder_exists:

            raise HTTPException(
                status_code=404,
                detail="Reminder not found",
            )

        # -------------------------------------------------
        # MARK AS SHOWN
        # -------------------------------------------------

        result = (
            mark_reminder_as_shown(
                reminder_id
            )
        )

        return {
            "success": True,
            "reminder": result,
        }

    except HTTPException:

        raise

    except Exception as error:

        print(
            "Failed to mark reminder as shown:",
            error,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to update reminder",
        )