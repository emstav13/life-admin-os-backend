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
    get_documents,
    get_document,
    delete_document,
    get_reminders,
    update_document,
)

from app.services.ai_service import (
    ask_document_question,
    generate_daily_briefing,
)


router = APIRouter()


# =========================================================
# REQUEST MODELS
# =========================================================


class AskRequest(BaseModel):
    document_id: str
    question: str


class AskAllRequest(BaseModel):
    question: str


class UpdateDocumentRequest(BaseModel):
    provider: str | None = None
    amount: str | None = None
    due_date: str | None = None
    priority: str | None = None


# =========================================================
# DASHBOARD STATS
# =========================================================


@router.get("/dashboard-stats")
async def dashboard_stats(
    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user.id

    try:
        documents = get_documents(
            user_id
        )

        reminders = get_reminders(
            user_id
        )

        high_priority = [
            document
            for document in documents
            if (
                document.get(
                    "ai_json",
                    {}
                ) or {}
            ).get("urgency") == "high"
        ]

        low_priority = [
            document
            for document in documents
            if (
                document.get(
                    "ai_json",
                    {}
                ) or {}
            ).get("urgency") == "low"
        ]

        return {
            "documents": len(documents),
            "high_priority": len(high_priority),
            "low_priority": len(low_priority),
            "notifications": len(reminders),
        }

    except Exception as error:
        print(
            "Dashboard stats error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard statistics",
        )


# =========================================================
# DAILY BRIEFING
# =========================================================


@router.get("/daily-briefing")
async def daily_briefing(
    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user.id

    # -----------------------------------------------------
    # GET ONLY THE AUTHENTICATED USER'S DOCUMENTS
    # -----------------------------------------------------

    try:
        documents = get_documents(
            user_id
        )

    except Exception as error:
        print(
            "Daily briefing database error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load documents for daily briefing",
        )

    # -----------------------------------------------------
    # SAFE DIAGNOSTICS
    #
    # Never log:
    # - user_id
    # - raw_text
    # - document contents
    # - email addresses
    # - access tokens
    # - secrets
    # -----------------------------------------------------

    print(
        "DAILY_BRIEFING_DOCUMENT_COUNT:",
        len(documents),
    )

    # -----------------------------------------------------
    # GENERATE BRIEFING
    #
    # generate_daily_briefing() is responsible for:
    # - selecting safe metadata
    # - sanitizing AI input
    # - excluding raw_text
    # - excluding user_id
    # - calling the AI service
    # -----------------------------------------------------

    try:
        briefing = generate_daily_briefing(
            documents
        )

    except Exception as error:
        print(
            "Daily briefing error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to generate daily briefing",
        )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "briefing": briefing or ""
    }


# =========================================================
# GET USER DOCUMENTS
# =========================================================


@router.get("/documents")
async def list_documents(
    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user.id

    try:
        return get_documents(
            user_id
        )

    except Exception as error:
        print(
            "List documents error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load documents",
        )


# =========================================================
# GET SINGLE DOCUMENT
# =========================================================


@router.get(
    "/documents/{document_id}"
)
async def document_detail(
    document_id: str,
    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user.id

    try:
        document = get_document(
            document_id,
            user_id,
        )

    except Exception as error:
        print(
            "Get document error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return document


# =========================================================
# UPDATE DOCUMENT
# =========================================================


@router.patch(
    "/documents/{document_id}"
)
async def edit_document(
    document_id: str,
    request: UpdateDocumentRequest,
    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user.id

    try:
        result = update_document(
            document_id=document_id,
            user_id=user_id,
            provider=request.provider,
            amount=request.amount,
            due_date=request.due_date,
            priority=request.priority,
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        return result

    except HTTPException:
        raise

    except Exception as error:
        print(
            "Update document error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to update document",
        )


# =========================================================
# DELETE DOCUMENT
# =========================================================


@router.delete(
    "/documents/{document_id}"
)
async def remove_document(
    document_id: str,
    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user.id

    try:
        result = delete_document(
            document_id=document_id,
            user_id=user_id,
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        return {
            "success": True,
            "deleted": result,
        }

    except HTTPException:
        raise

    except Exception as error:
        print(
            "Delete document error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to delete document",
        )


# =========================================================
# ASK ABOUT ONE DOCUMENT
# =========================================================


@router.post(
    "/ask-document"
)
async def ask_document(
    request: AskRequest,
    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user.id

    try:
        document = get_document(
            request.document_id,
            user_id,
        )

    except Exception as error:
        print(
            "Ask document lookup error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    raw_text = document.get(
        "raw_text",
        "",
    )

    if not raw_text:
        raise HTTPException(
            status_code=400,
            detail="Document has no readable text",
        )

    try:
        answer = ask_document_question(
            raw_text,
            request.question,
        )

        return {
            "answer": answer
        }

    except Exception as error:
        print(
            "Ask document AI error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to process AI request",
        )


# =========================================================
# ASK ABOUT ALL USER DOCUMENTS
# =========================================================


@router.post(
    "/ask-all-documents"
)
async def ask_all_documents(
    request: AskAllRequest,
    current_user=Depends(
        get_current_user
    ),
):
    user_id = current_user.id

    try:
        documents = get_documents(
            user_id
        )

    except Exception as error:
        print(
            "Ask all documents lookup error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to load documents",
        )

    if not documents:
        return {
            "answer": (
                "You don't have any documents yet."
            )
        }

    combined_parts = []

    for document in documents:
        ai_json = (
            document.get(
                "ai_json",
                {}
            ) or {}
        )

        combined_parts.append(
            f"""
Filename:
{document.get("filename", "Unknown")}

Type:
{document.get("document_type", "Unknown")}

Provider:
{ai_json.get("provider", "Unknown")}

Due Date:
{ai_json.get("due_date", "Unknown")}

Urgency:
{ai_json.get("urgency", "Unknown")}

Summary:
{document.get(
    "summary",
    "No summary available."
)}

Document Text:
{document.get("raw_text", "")}
"""
        )

    combined_text = "\n\n".join(
        combined_parts
    )

    try:
        answer = ask_document_question(
            combined_text,
            request.question,
        )

        return {
            "answer": answer
        }

    except Exception as error:
        print(
            "Ask all documents AI error:",
            type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to process AI request",
        )