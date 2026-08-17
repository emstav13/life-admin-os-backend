import asyncio
import os

from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from app.services.db_service import (
    get_all_pending_email_reminders,
    get_user_email,
    mark_reminder_email_sent,
    update_reminder_for_next_occurrence,
)

from app.services.email_service import (
    send_reminder_email,
)


REMINDER_TIMEZONE = os.getenv(
    "REMINDER_TIMEZONE",
    "Europe/Athens",
)


def _now_local():
    try:
        return datetime.now(
            ZoneInfo(REMINDER_TIMEZONE)
        )
    except Exception:
        return datetime.now()


# =========================================================
# CALCULATE NEXT OCCURRENCE
# =========================================================

def calculate_next_date(
    current_date: str,
    repeat_type: str,
) -> str | None:

    try:
        date = datetime.fromisoformat(
            current_date
        )
    except Exception as error:
        print(
            "Invalid repeat date:",
            type(error).__name__,
        )
        return None

    repeat_type = (
        repeat_type or "none"
    ).lower()

    if repeat_type == "daily":
        next_date = date + relativedelta(days=1)
    elif repeat_type == "weekly":
        next_date = date + relativedelta(weeks=1)
    elif repeat_type == "monthly":
        next_date = date + relativedelta(months=1)
    else:
        return None

    return next_date.strftime("%Y-%m-%d")


# =========================================================
# CHECK REMINDERS
# =========================================================

async def check_reminders():

    print(
        f"Reminder scheduler is running "
        f"(timezone={REMINDER_TIMEZONE})"
    )

    while True:
        try:
            reminders = (
                get_all_pending_email_reminders()
            )

            now = _now_local()

            print(
                f"Checking reminders: {len(reminders)} pending"
            )

            for reminder in reminders:

                user_id = reminder.get("user_id")

                if not user_id:
                    continue

                if not reminder.get(
                    "email_notification"
                ):
                    continue

                if reminder.get("email_sent"):
                    continue

                due_date = reminder.get("due_date")
                reminder_time = reminder.get(
                    "reminder_time"
                )

                if not due_date:
                    continue

                try:
                    date_string = str(due_date)

                    if reminder_time:
                        time_string = str(
                            reminder_time
                        )

                        if len(time_string) == 5:
                            time_string = (
                                f"{time_string}:00"
                            )

                        reminder_datetime = (
                            datetime.fromisoformat(
                                f"{date_string}T{time_string}"
                            )
                        )
                    else:
                        reminder_datetime = (
                            datetime.fromisoformat(
                                f"{date_string}T00:00:00"
                            )
                        )

                except Exception as error:
                    print(
                        "Invalid reminder date:",
                        type(error).__name__,
                    )
                    continue

                if now.replace(
                    tzinfo=None
                ) < reminder_datetime:
                    continue

                user_email = get_user_email(
                    user_id
                )

                if not user_email:
                    print(
                        "No email found for reminder user"
                    )
                    continue

                result = send_reminder_email(
                    to_email=user_email,
                    document_name=(
                        reminder.get(
                            "document_name",
                            "Document",
                        )
                    ),
                    message=(
                        reminder.get(
                            "message",
                            "You have a reminder from Life AiOS.",
                        )
                    ),
                    reminder_date=(
                        reminder.get("due_date")
                    ),
                    reminder_time=(
                        reminder.get("reminder_time")
                    ),
                )

                if not result:
                    # Leave email_sent=False so the scheduler
                    # can retry on the next cycle.
                    continue

                repeat_type = (
                    reminder.get(
                        "repeat_type",
                        "none",
                    )
                    or "none"
                ).lower()

                if repeat_type != "none":
                    next_date = calculate_next_date(
                        date_string,
                        repeat_type,
                    )

                    if next_date:
                        update_reminder_for_next_occurrence(
                            reminder_id=reminder["id"],
                            next_due_date=next_date,
                            user_id=user_id,
                        )
                else:
                    mark_reminder_email_sent(
                        reminder["id"],
                        user_id,
                    )

        except Exception as error:
            print(
                "Reminder checker error:",
                type(error).__name__,
            )

        await asyncio.sleep(60)
