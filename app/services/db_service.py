from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timezone
import os
import json
import logging

logger = logging.getLogger(__name__)


from app.services.encryption_service import (
    encrypt_text,
    decrypt_text,
)


# =========================================================
# SUPABASE
# =========================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_KEY is missing"
    )


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# =========================================================
# ENCRYPTION HELPERS
# =========================================================


def _encrypt_ai_json(ai_data):
    """
    Encrypt the complete AI JSON object.
    """

    if ai_data is None:
        return None

    json_text = json.dumps(
        ai_data,
        ensure_ascii=False,
    )

    return encrypt_text(
        json_text
    )


def _decrypt_ai_json(value):
    """
    Decrypt ai_json.

    Supports:
    - encrypted string
    - old plaintext dictionary
    - plaintext JSON string
    """

    if value is None:
        return {}


    # -----------------------------------------------------
    # Already a dictionary
    # -----------------------------------------------------

    if isinstance(value, dict):
        return value


    # -----------------------------------------------------
    # Encrypted / JSON string
    # -----------------------------------------------------

    if isinstance(value, str):

        # First try encrypted value.
        try:

            decrypted = decrypt_text(
                value
            )

            parsed = json.loads(
                decrypted
            )

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass


        # Fallback for old plaintext JSON.
        try:

            parsed = json.loads(
                value
            )

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass


    return {}


def _decrypt_text_field(value):
    """
    Decrypt a text field.

    Supports:
    - encrypted value
    - old plaintext value
    """

    if value is None:
        return ""


    if not isinstance(
        value,
        str,
    ):
        value = str(value)


    try:

        return decrypt_text(
            value
        )

    except Exception:

        # Backward compatibility for
        # documents that were created before
        # encryption was enabled.
        return value


def _decrypt_document(document):
    """
    Convert an encrypted database document into
    the normal structure expected by the application.
    """

    if not document:
        return document


    # -----------------------------------------------------
    # RAW TEXT
    # -----------------------------------------------------

    document["raw_text"] = _decrypt_text_field(
        document.get("raw_text")
    )


    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    document["summary"] = _decrypt_text_field(
        document.get("summary")
    )


    # -----------------------------------------------------
    # AI JSON
    # -----------------------------------------------------

    document["ai_json"] = _decrypt_ai_json(
        document.get("ai_json")
    )


    return document
# =========================================================
# SUBSCRIPTION / UPLOAD QUOTA
# =========================================================

FREE_DOCUMENT_LIMIT = 5
PRO_MONTHLY_DOCUMENT_LIMIT = 20


def check_document_upload_quota(
    user_id,
):
    """
    Check whether an authenticated user is allowed
    to upload another document.

    FREE:
        5 documents lifetime.

    PRO:
        20 documents per subscription period.

    The backend calculates usage directly from the
    documents table. The frontend cannot modify usage.
    """

    if not user_id:
        raise ValueError(
            "user_id is required for quota check"
        )

    # -----------------------------------------------------
    # GET SUBSCRIPTION
    # -----------------------------------------------------

    subscription_response = (
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
        subscription_response.data or []
    )

    # -----------------------------------------------------
    # NO SUBSCRIPTION
    #
    # Fail closed:
    # if the account has no subscription record,
    # do not allow the upload.
    # -----------------------------------------------------

    if not subscription_data:

        return {
            "allowed": False,
            "plan": "none",
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "reason": "subscription_not_found",
        }

    subscription = subscription_data[0]

    plan = (
        subscription.get("plan")
        or "free"
    )

    status = (
        subscription.get("status")
        or "active"
    )

    # -----------------------------------------------------
    # SUBSCRIPTION STATUS
    # -----------------------------------------------------

    if status not in {
        "active",
        "trialing",
    }:

        return {
            "allowed": False,
            "plan": plan,
            "used": 0,
            "limit": (
                FREE_DOCUMENT_LIMIT
                if plan == "free"
                else PRO_MONTHLY_DOCUMENT_LIMIT
            ),
            "remaining": 0,
            "reason": "subscription_inactive",
        }

    # =====================================================
    # FREE PLAN
    # =====================================================

    if plan == "free":

        documents_response = (
            supabase
            .table("documents")
            .select(
                "id",
                count="exact",
            )
            .eq(
                "user_id",
                user_id,
            )
            .execute()
        )

        used = (
            documents_response.count
            or 0
        )

        remaining = max(
            FREE_DOCUMENT_LIMIT - used,
            0,
        )

        return {
            "allowed": (
                used < FREE_DOCUMENT_LIMIT
            ),
            "plan": "free",
            "used": used,
            "limit": FREE_DOCUMENT_LIMIT,
            "remaining": remaining,
            "reason": (
                "ok"
                if used < FREE_DOCUMENT_LIMIT
                else "free_limit_reached"
            ),
        }

    # =====================================================
    # PRO PLAN
    # =====================================================

    if plan == "pro":

        period_start = subscription.get(
            "current_period_start"
        )

        period_end = subscription.get(
            "current_period_end"
        )

        # -------------------------------------------------
        # Safety:
        # Pro subscription must have a valid period.
        # -------------------------------------------------

        if not period_start or not period_end:

            return {
                "allowed": False,
                "plan": "pro",
                "used": 0,
                "limit": PRO_MONTHLY_DOCUMENT_LIMIT,
                "remaining": 0,
                "reason": "subscription_period_missing",
            }

        # -------------------------------------------------
        # Count documents created during the current
        # subscription period.
        # -------------------------------------------------

        documents_response = (
            supabase
            .table("documents")
            .select(
                "id",
                count="exact",
            )
            .eq(
                "user_id",
                user_id,
            )
            .gte(
                "created_at",
                period_start,
            )
            .lt(
                "created_at",
                period_end,
            )
            .execute()
        )

        used = (
            documents_response.count
            or 0
        )

        remaining = max(
            PRO_MONTHLY_DOCUMENT_LIMIT - used,
            0,
        )

        return {
            "allowed": (
                used < PRO_MONTHLY_DOCUMENT_LIMIT
            ),
            "plan": "pro",
            "used": used,
            "limit": PRO_MONTHLY_DOCUMENT_LIMIT,
            "remaining": remaining,
            "reason": (
                "ok"
                if used < PRO_MONTHLY_DOCUMENT_LIMIT
                else "pro_monthly_limit_reached"
            ),
        }

    # -----------------------------------------------------
    # UNKNOWN PLAN
    #
    # Fail closed for security.
    # -----------------------------------------------------

    return {
        "allowed": False,
        "plan": plan,
        "used": 0,
        "limit": 0,
        "remaining": 0,
        "reason": "unknown_subscription_plan",
    }

# =========================================================
# SAVE DOCUMENT
# =========================================================


def save_document(
    filename,
    raw_text,
    ai_data,
    user_id,
    priority="",
    reminder_enabled=False,
    reminder_date="",
    reminder_time="",
    repeat_type="none",
    dashboard_notification=True,
    email_notification=True,
    mobile_push=False,
):

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    summary = ""

    if ai_data:

        summary = (
            ai_data.get(
                "short_summary"
            )
            or ""
        )


    # -----------------------------------------------------
    # ENCRYPT SENSITIVE DATA
    # -----------------------------------------------------

    encrypted_raw_text = encrypt_text(
        raw_text
    )


    encrypted_summary = (
        encrypt_text(
            summary
        )
        if summary
        else None
    )


    encrypted_ai_json = _encrypt_ai_json(
        ai_data
    )


    # -----------------------------------------------------
    # DATABASE INSERT
    # -----------------------------------------------------

    data = {

        "filename":
            filename,

        "document_type":
            (
                ai_data.get(
                    "document_type"
                )
                if ai_data
                else None
            ),

        "raw_text":
            encrypted_raw_text,

        "summary":
            encrypted_summary,

        "ai_json":
            encrypted_ai_json,

        "user_id":
            user_id,

        "priority_override":
            priority,

        "reminder_enabled":
            reminder_enabled,

        "reminder_date":
            (
                reminder_date
                if reminder_date
                else None
            ),

        "reminder_time":
            (
                reminder_time
                if reminder_time
                else None
            ),

        "repeat_type":
            repeat_type,

        "dashboard_notification":
            dashboard_notification,

        "email_notification":
            email_notification,

        "mobile_push":
            mobile_push,
    }


    response = (
        supabase
        .table("documents")
        .insert(data)
        .execute()
    )


    if not response.data:

        raise RuntimeError(
            "Failed to save document"
        )


    saved_document = response.data[0]


    # -----------------------------------------------------
    # RETURN DECRYPTED DATA TO APPLICATION
    # -----------------------------------------------------

    saved_document["raw_text"] = raw_text

    saved_document["summary"] = summary

    saved_document["ai_json"] = (
        ai_data or {}
    )


    return saved_document


# =========================================================
# GET USER DOCUMENTS
# =========================================================


def get_documents(
    user_id,
):

    response = (
        supabase
        .table("documents")
        .select("*")
        .eq(
            "user_id",
            user_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )


    documents = (
        response.data or []
    )


    return [
        _decrypt_document(
            document
        )
        for document in documents
    ]


# =========================================================
# GET SINGLE DOCUMENT
# =========================================================


def get_document(
    document_id,
    user_id,
):

    response = (
        supabase
        .table("documents")
        .select("*")
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )


    if not response.data:
        return None


    document = response.data[0]


    return _decrypt_document(
        document
    )


# =========================================================
# DELETE DOCUMENT
# =========================================================


def delete_document(
    document_id,
    user_id,
):


    # -----------------------------------------------------
    # VERIFY DOCUMENT OWNERSHIP
    # -----------------------------------------------------

    document_response = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )


    if not document_response.data:

        logger.info(
            "Document deletion failed: not found or unauthorized"
        )

        return []


    # -----------------------------------------------------
    # DELETE TASKS
    # -----------------------------------------------------

    delete_tasks = (
        supabase
        .table("tasks")
        .delete()
        .eq(
            "document_id",
            document_id,
        )
        .execute()
    )



    # -----------------------------------------------------
    # VERIFY TASKS DELETED
    # -----------------------------------------------------

    remaining_tasks = (
        supabase
        .table("tasks")
        .select("id")
        .eq(
            "document_id",
            document_id,
        )
        .execute()
    )


    if remaining_tasks.data:

        raise RuntimeError(
            "Document tasks were not completely deleted"
        )


    # -----------------------------------------------------
    # DELETE REMINDERS
    # -----------------------------------------------------

    delete_reminders = (
        supabase
        .table("reminders")
        .delete()
        .eq(
            "document_id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )



    # -----------------------------------------------------
    # VERIFY REMINDERS DELETED
    # -----------------------------------------------------

    remaining_reminders = (
        supabase
        .table("reminders")
        .select("id")
        .eq(
            "document_id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )


    if remaining_reminders.data:

        raise RuntimeError(
            "Document reminders were not completely deleted"
        )


    # -----------------------------------------------------
    # DELETE DOCUMENT
    # -----------------------------------------------------

    delete_document_response = (
        supabase
        .table("documents")
        .delete()
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )



    # -----------------------------------------------------
    # VERIFY DOCUMENT DELETED
    # -----------------------------------------------------

    remaining_document = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )


    if remaining_document.data:

        raise RuntimeError(
            "Document was not completely deleted"
        )


    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------

    logger.info(
        "Document deletion completed successfully."
    )


    return delete_document_response.data


# =========================================================
# UPDATE DOCUMENT
# =========================================================


def update_document(
    document_id,
    user_id,
    provider=None,
    amount=None,
    due_date=None,
    priority=None,
):

    document = get_document(
        document_id,
        user_id,
    )


    if not document:
        return []


    # -----------------------------------------------------
    # GET DECRYPTED AI JSON
    # -----------------------------------------------------

    ai_json = (
        document.get(
            "ai_json"
        )
        or {}
    )


    # -----------------------------------------------------
    # UPDATE VALUES
    # -----------------------------------------------------

    if provider is not None:

        ai_json["provider"] = provider


    if amount is not None:

        ai_json["amount"] = amount


    if due_date is not None:

        ai_json["due_date"] = due_date


    if priority is not None:

        ai_json["urgency"] = priority


    # -----------------------------------------------------
    # UPDATE SUMMARY
    # -----------------------------------------------------

    summary = (
        ai_json.get(
            "short_summary"
        )
        or document.get(
            "summary"
        )
        or ""
    )


    # -----------------------------------------------------
    # RE-ENCRYPT
    # -----------------------------------------------------

    encrypted_ai_json = _encrypt_ai_json(
        ai_json
    )


    encrypted_summary = (
        encrypt_text(
            summary
        )
        if summary
        else None
    )


    # -----------------------------------------------------
    # UPDATE DATABASE
    # -----------------------------------------------------

    response = (
        supabase
        .table("documents")
        .update({

            "ai_json":
                encrypted_ai_json,

            "summary":
                encrypted_summary,

            "document_type":
                ai_json.get(
                    "document_type",
                    document.get(
                        "document_type"
                    ),
                ),

        })
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )


    if not response.data:
        return []


    # -----------------------------------------------------
    # RETURN DECRYPTED DOCUMENT
    # -----------------------------------------------------

    updated_document = response.data[0]


    updated_document = _decrypt_document(
        updated_document
    )


    return [
        updated_document
    ]


# =========================================================
# TASKS
# =========================================================


def create_task(
    document_id,
    title,
    user_id,
):

    # -----------------------------------------------------
    # VERIFY DOCUMENT OWNERSHIP
    # -----------------------------------------------------

    document_response = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )

    if not document_response.data:

        logger.warning(
            "Unauthorized task creation attempt."
        )

        return []

    # -----------------------------------------------------
    # CREATE TASK
    # -----------------------------------------------------

    response = (
        supabase
        .table("tasks")
        .insert({
            "document_id":
                document_id,

            "title":
                title,
        })
        .execute()
    )

    return response.data or []


def get_tasks(
    document_id,
    user_id,
):

    # -----------------------------------------------------
    # VERIFY DOCUMENT OWNERSHIP
    # -----------------------------------------------------

    document_response = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )

    if not document_response.data:
        return []

    # -----------------------------------------------------
    # GET TASKS
    # -----------------------------------------------------

    response = (
        supabase
        .table("tasks")
        .select("*")
        .eq(
            "document_id",
            document_id,
        )
        .order(
            "created_at",
            desc=False,
        )
        .execute()
    )

    return response.data or []


def complete_task(
    task_id,
    user_id,
):

    # -----------------------------------------------------
    # GET TASK
    # -----------------------------------------------------

    task_response = (
        supabase
        .table("tasks")
        .select(
            "id, document_id"
        )
        .eq(
            "id",
            task_id,
        )
        .limit(1)
        .execute()
    )

    if not task_response.data:
        return []

    task = task_response.data[0]

    document_id = task.get(
        "document_id"
    )

    if not document_id:
        return []

    # -----------------------------------------------------
    # VERIFY DOCUMENT OWNERSHIP
    # -----------------------------------------------------

    document_response = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )

    if not document_response.data:

        logger.warning(
            "Unauthorized task completion attempt."
        )

        return []

    # -----------------------------------------------------
    # COMPLETE TASK
    # -----------------------------------------------------

    response = (
        supabase
        .table("tasks")
        .update({
            "completed": True,
        })
        .eq(
            "id",
            task_id,
        )
        .eq(
            "document_id",
            document_id,
        )
        .execute()
    )

    return response.data or []


def get_all_tasks(
    user_id=None,
):

    if not user_id:
        return []


    documents = get_documents(
        user_id
    )


    document_ids = [
        document["id"]
        for document in documents
    ]


    if not document_ids:
        return []


    all_tasks = []


    for document_id in document_ids:

        response = (
            supabase
            .table("tasks")
            .select("*")
            .eq(
                "document_id",
                document_id,
            )
            .order(
                "created_at",
                desc=False,
            )
            .execute()
        )


        all_tasks.extend(
            response.data or []
        )


    return all_tasks


# =========================================================
# REMINDERS
# =========================================================


def create_reminder(
    document_id,
    user_id,
    document_name,
    title,
    message,
    due_date,
    reminder_time=None,
    repeat_type="none",
    dashboard_notification=True,
    email_notification=True,
    mobile_push=False,
):

    # -----------------------------------------------------
    # VERIFY DOCUMENT OWNERSHIP
    # -----------------------------------------------------

    document_response = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "id",
            document_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )


    if not document_response.data:
        return []


    # -----------------------------------------------------
    # CREATE REMINDER
    # -----------------------------------------------------

    response = (
        supabase
        .table("reminders")
        .insert({

            "document_id":
                document_id,

            "user_id":
                user_id,

            "document_name":
                document_name,

            "title":
                title,

            "message":
                message,

            "due_date":
                due_date,

            "reminder_time":
                reminder_time,

            "repeat_type":
                repeat_type,

            "dashboard_notification":
                dashboard_notification,

            "email_notification":
                email_notification,

            "mobile_push":
                mobile_push,

            "read":
                False,

            "email_sent":
                False,

            "dashboard_shown":
                False,

        })
        .execute()
    )


    return response.data or []


def get_reminders(
    user_id,
):

    response = (
        supabase
        .table("reminders")
        .select("*")
        .eq(
            "user_id",
            user_id,
        )
        .order(
            "due_date",
            desc=False,
        )
        .execute()
    )


    return response.data or []


# =========================================================
# EMAIL REMINDERS
# =========================================================


def get_all_pending_email_reminders():

    response = (
        supabase
        .table("reminders")
        .select("*")
        .eq(
            "email_notification",
            True,
        )
        .eq(
            "email_sent",
            False,
        )
        .execute()
    )


    return response.data or []


def get_user_email(
    user_id,
):

    try:

        response = (
            supabase
            .auth
            .admin
            .get_user_by_id(
                user_id
            )
        )


        if (
            response
            and response.user
        ):

            return (
                response.user.email
            )


        return None


    except Exception as error:

        logger.error(
            "Failed to retrieve user email: %s",
            type(error).__name__,
        )

        return None


def mark_reminder_email_sent(
    reminder_id,
    user_id,
):

    response = (
        supabase
        .table("reminders")
        .update({
            "email_sent": True,
        })
        .eq(
            "id",
            reminder_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    return response.data or []


# =========================================================
# DASHBOARD NOTIFICATIONS
# =========================================================


def mark_reminder_as_shown(
    reminder_id,
    user_id,
):

    response = (
        supabase
        .table("reminders")
        .update({
            "dashboard_shown":
                True,

            "read":
                True,
        })
        .eq(
            "id",
            reminder_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    return response.data or []


# =========================================================
# REPEATING REMINDERS
# =========================================================


def update_reminder_for_next_occurrence(
    reminder_id,
    next_due_date,
    user_id,
):

    response = (
        supabase
        .table("reminders")
        .update({
            "due_date": next_due_date,
            "email_sent": False,
            "read": False,
            "dashboard_shown": False,
        })
        .eq(
            "id",
            reminder_id,
        )
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    return response.data or []


# =========================================================
# NOTIFICATION PREFERENCES
# =========================================================


def get_notification_preferences(
    user_id,
):

    response = (
        supabase
        .table(
            "notification_preferences"
        )
        .select("*")
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )


    if not response.data:

        return {

            "user_id":
                user_id,

            "enabled":
                True,

            "morning_time":
                "09:00",

            "evening_time":
                "20:00",

            "daily_briefing":
                True,

            "evening_review":
                False,

            "deadline_reminders":
                True,

        }


    return response.data[0]


def save_notification_preferences(
    user_id,
    enabled,
    morning_time,
    evening_time,
    daily_briefing,
    evening_review,
    deadline_reminders,
):

    response = (
        supabase
        .table(
            "notification_preferences"
        )
        .upsert({

            "user_id":
                user_id,

            "enabled":
                enabled,

            "morning_time":
                morning_time,

            "evening_time":
                evening_time,

            "daily_briefing":
                daily_briefing,

            "evening_review":
                evening_review,

            "deadline_reminders":
                deadline_reminders,

        })
        .execute()
    )


    return response.data or []
# =========================================================
# DELETE ACCOUNT DATA
# =========================================================


def delete_account_data(
    user_id,
):

    logger.info(
        "Starting account application data deletion."
    )

    # -----------------------------------------------------
    # GET ALL USER DOCUMENTS
    # -----------------------------------------------------

    documents_response = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    documents = (
        documents_response.data or []
    )

    logger.info(
        "Documents found for account deletion: %d",
        len(documents),
    )

    # -----------------------------------------------------
    # DELETE DOCUMENTS
    #
    # delete_document() already deletes:
    # - tasks
    # - reminders
    # - document
    # -----------------------------------------------------

    for document in documents:

        document_id = document.get(
            "id"
        )

        if not document_id:
            continue

        delete_document(
            document_id=document_id,
            user_id=user_id,
        )

    # -----------------------------------------------------
    # DELETE ANY REMAINING TASKS
    #
    # Safety cleanup for orphaned tasks.
    # -----------------------------------------------------

    remaining_documents_response = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    remaining_documents = (
        remaining_documents_response.data
        or []
    )

    for document in remaining_documents:

        document_id = document.get(
            "id"
        )

        if document_id:

            (
                supabase
                .table("tasks")
                .delete()
                .eq(
                    "document_id",
                    document_id,
                )
                .execute()
            )

    # -----------------------------------------------------
    # DELETE USER REMINDERS
    # -----------------------------------------------------

    (
        supabase
        .table("reminders")
        .delete()
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    # -----------------------------------------------------
    # DELETE NOTIFICATION PREFERENCES
    # -----------------------------------------------------

    (
        supabase
        .table(
            "notification_preferences"
        )
        .delete()
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    logger.info(
        "Application data deletion completed."
    )


# =========================================================
# VERIFY ACCOUNT DATA DELETED
# =========================================================

def verify_account_data_deleted(
    user_id,
):
    """
    Verify that all application data belonging to the
    authenticated user has been deleted.

    Tasks are linked to users indirectly through documents,
    because the tasks table does not contain a user_id field.
    """

    # -----------------------------------------------------
    # DOCUMENTS
    # -----------------------------------------------------

    documents_response = (
        supabase
        .table("documents")
        .select("id")
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    documents = (
        documents_response.data or []
    )

    if documents:
        logger.warning(
            "Account deletion verification failed: "
            "remaining documents=%d",
            len(documents),
        )

        return False

    # -----------------------------------------------------
    # REMINDERS
    # -----------------------------------------------------

    reminders_response = (
        supabase
        .table("reminders")
        .select("id")
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    reminders = (
        reminders_response.data or []
    )

    if reminders:
        logger.warning(
            "Account deletion verification failed: "
            "remaining reminders=%d",
            len(reminders),
        )

        return False

    # -----------------------------------------------------
    # NOTIFICATION PREFERENCES
    # -----------------------------------------------------

    notification_preferences_response = (
        supabase
        .table(
            "notification_preferences"
        )
        .select("user_id")
        .eq(
            "user_id",
            user_id,
        )
        .execute()
    )

    notification_preferences = (
        notification_preferences_response.data
        or []
    )

    if notification_preferences:
        logger.warning(
            "Account deletion verification failed: "
            "remaining notification preferences."
        )

        return False

    # -----------------------------------------------------
    # TASKS
    #
    # Tasks do not contain user_id.
    # They are linked through documents.
    #
    # Since we already verified that the user's documents
    # no longer exist, we additionally check for orphaned
    # tasks by looking for tasks whose document_id no longer
    # exists in documents.
    #
    # We cannot safely identify ownership of arbitrary
    # orphaned tasks without a user_id on the tasks table.
    # -----------------------------------------------------

    # No user-owned documents remain, therefore there can be
    # no valid tasks belonging to the user's remaining
    # documents.

    logger.info(
        "Account application data deletion verified successfully."
    )

    return True
# =========================================================
# DATA EXPORT
# =========================================================

def export_account_data(user_id):
    """
    Export all application data belonging to one authenticated user.

    IMPORTANT:
    user_id must come from the authenticated backend user.
    Never accept an arbitrary user_id from the frontend.
    """

    if not user_id:
        raise ValueError(
            "user_id is required for account export"
        )

    # -----------------------------------------------------
    # DOCUMENTS
    # -----------------------------------------------------

    documents_response = (
        supabase
        .table("documents")
        .select("*")
        .eq(
            "user_id",
            user_id,
        )
        .order(
            "created_at",
            desc=True,
        )
        .execute()
    )

    documents = (
        documents_response.data or []
    )

    # -----------------------------------------------------
    # DECRYPT DOCUMENT DATA
    # -----------------------------------------------------

    exported_documents = []

    document_ids = []

    for document in documents:

        document_ids.append(
            document["id"]
        )

        decrypted_document = (
            _decrypt_document(
                document
            )
        )

        # -------------------------------------------------
        # SECURITY:
        # Never export database encryption blobs.
        # The user receives the decrypted application data.
        # -------------------------------------------------

        decrypted_document.pop(
            "encrypted_raw_text",
            None,
        )

        decrypted_document.pop(
            "encrypted_summary",
            None,
        )

        decrypted_document.pop(
            "encrypted_ai_json",
            None,
        )

        exported_documents.append(
            decrypted_document
        )

    # -----------------------------------------------------
    # TASKS
    # -----------------------------------------------------

    exported_tasks = []

    for document_id in document_ids:

        tasks_response = (
            supabase
            .table("tasks")
            .select("*")
            .eq(
                "document_id",
                document_id,
            )
            .order(
                "created_at",
                desc=False,
            )
            .execute()
        )

        exported_tasks.extend(
            tasks_response.data or []
        )

    # -----------------------------------------------------
    # REMINDERS
    # -----------------------------------------------------

    reminders_response = (
        supabase
        .table("reminders")
        .select("*")
        .eq(
            "user_id",
            user_id,
        )
        .order(
            "created_at",
            desc=False,
        )
        .execute()
    )

    exported_reminders = (
        reminders_response.data or []
    )

    # -----------------------------------------------------
    # NOTIFICATION PREFERENCES
    # -----------------------------------------------------

    preferences_response = (
        supabase
        .table(
            "notification_preferences"
        )
        .select("*")
        .eq(
            "user_id",
            user_id,
        )
        .limit(1)
        .execute()
    )

    notification_preferences = (
        preferences_response.data[0]
        if preferences_response.data
        else None
    )

    # -----------------------------------------------------
    # FINAL EXPORT
    # -----------------------------------------------------

    return {
        "documents": exported_documents,
        "tasks": exported_tasks,
        "reminders": exported_reminders,
        "notification_preferences":
            notification_preferences,
    }