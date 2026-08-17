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
    current_user=Depends(get_current_user),
):
    user_id = current_user.id

    try:
        return get_reminders(user_id)

    except Exception as error:
        print(
            "Failed to load reminders:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load reminders",
        )


# =========================================================
# MARK REMINDER AS SHOWN
# =========================================================

@router.patch("/reminders/{reminder_id}/shown")
async def mark_reminder_shown(
    reminder_id: str,
    current_user=Depends(get_current_user),
):
    user_id = current_user.id

    try:
        reminders = get_reminders(user_id)

        reminder_exists = any(
            str(reminder.get("id")) == str(reminder_id)
            for reminder in reminders
        )

        if not reminder_exists:
            raise HTTPException(
                status_code=404,
                detail="Reminder not found",
            )

        # IMPORTANT:
        # Pass user_id because the DB function performs
        # an ownership-scoped update.
        result = mark_reminder_as_shown(
            reminder_id,
            user_id,
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
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to update reminder",
        )