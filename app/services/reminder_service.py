import asyncio

from datetime import datetime

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

    # =====================================================
    # DAILY
    # =====================================================

    if repeat_type == "daily":

        next_date = (
            date
            + relativedelta(
                days=1
            )
        )

    # =====================================================
    # WEEKLY
    # =====================================================

    elif repeat_type == "weekly":

        next_date = (
            date
            + relativedelta(
                weeks=1
            )
        )

    # =====================================================
    # MONTHLY
    # =====================================================

    elif repeat_type == "monthly":

        next_date = (
            date
            + relativedelta(
                months=1
            )
        )

    # =====================================================
    # NON-RECURRING
    # =====================================================

    else:

        return None

    return next_date.strftime(
        "%Y-%m-%d"
    )


# =========================================================
# CHECK REMINDERS
# =========================================================

async def check_reminders():

    print(
        "Reminder scheduler is running"
    )

    while True:

        try:

            reminders = (
                get_all_pending_email_reminders()
            )

            now = datetime.now()

            print(
                f"Checking reminders: {len(reminders)} pending"
            )

            # =================================================
            # PROCESS REMINDERS
            # =================================================

            for reminder in reminders:

                # =============================================
                # GET USER ID
                # =============================================

                user_id = reminder.get(
                    "user_id"
                )

                if not user_id:

                    print(
                        "Reminder skipped: missing user_id"
                    )

                    continue

                # =============================================
                # EMAIL NOTIFICATION ENABLED?
                # =============================================

                if not reminder.get(
                    "email_notification"
                ):

                    continue

                # =============================================
                # ALREADY SENT?
                # =============================================

                if reminder.get(
                    "email_sent"
                ):

                    continue

                # =============================================
                # REMINDER DATE
                # =============================================

                due_date = reminder.get(
                    "due_date"
                )

                reminder_time = reminder.get(
                    "reminder_time"
                )

                if not due_date:

                    continue

                # =============================================
                # BUILD REMINDER DATETIME
                # =============================================

                try:

                    date_string = str(
                        due_date
                    )

                    if reminder_time:

                        time_string = str(
                            reminder_time
                        )

                        # Support:
                        # 10:30
                        # 10:30:00

                        if len(
                            time_string
                        ) == 5:

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

                # =============================================
                # NOT DUE YET
                # =============================================

                if now < reminder_datetime:

                    continue

                # =============================================
                # GET USER EMAIL
                # =============================================

                user_email = get_user_email(
                    user_id
                )

                if not user_email:

                    print(
                        "No email found for reminder user"
                    )

                    continue

                # =============================================
                # SEND EMAIL
                # =============================================

                result = (
                    send_reminder_email(
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
                                (
                                    "You have a reminder "
                                    "from Life AiOS."
                                ),
                            )
                        ),

                        reminder_date=(
                            reminder.get(
                                "due_date"
                            )
                        ),

                        reminder_time=(
                            reminder.get(
                                "reminder_time"
                            )
                        ),
                    )
                )

                # =============================================
                # EMAIL SENT SUCCESSFULLY
                # =============================================

                if result:

                    repeat_type = (
                        reminder.get(
                            "repeat_type",
                            "none",
                        )
                        or "none"
                    ).lower()

                    # =========================================
                    # RECURRING REMINDER
                    # =========================================

                    if repeat_type != "none":

                        next_date = (
                            calculate_next_date(
                                date_string,
                                repeat_type,
                            )
                        )

                        if next_date:

                            update_reminder_for_next_occurrence(
                                reminder_id=(
                                    reminder["id"]
                                ),

                                next_due_date=(
                                    next_date
                                ),

                                user_id=(
                                    user_id
                                ),
                            )

                            print(
                                "Recurring reminder scheduled:",
                                reminder["id"],
                                "->",
                                next_date,
                            )

                        else:

                            mark_reminder_email_sent(
                                reminder["id"],
                                user_id,
                            )

                    # =========================================
                    # ONE-TIME REMINDER
                    # =========================================

                    else:

                        mark_reminder_email_sent(
                            reminder["id"],
                            user_id,
                        )

                        print(
                            "Reminder email marked as sent:",
                            reminder["id"],
                        )

        except Exception as error:

            # =================================================
            # SECURITY:
            # Never log reminder contents,
            # email addresses, tokens or secrets.
            # =================================================

            print(
                "Reminder checker error:",
                type(error).__name__,
            )

        # =====================================================
        # CHECK EVERY 60 SECONDS
        # =====================================================

        await asyncio.sleep(
            60
        )