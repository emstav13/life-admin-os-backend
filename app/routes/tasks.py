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
    create_task,
    get_tasks,
    complete_task,
)


router = APIRouter()


# =========================================================
# REQUEST MODELS
# =========================================================

class TaskRequest(BaseModel):
    document_id: str
    title: str


# =========================================================
# MARK TASK AS COMPLETE
# =========================================================

@router.patch(
    "/tasks/{task_id}/complete"
)
async def mark_complete(
    task_id: str,
    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user.id

    try:

        result = complete_task(
            task_id=task_id,
            user_id=user_id,
        )

        if not result:

            raise HTTPException(
                status_code=404,
                detail="Task not found",
            )

        return {
            "success": True,
            "task": result,
        }

    except HTTPException:

        raise

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Failed to complete task",
        )


# =========================================================
# CREATE TASK
# =========================================================

@router.post("/tasks")
async def add_task(
    request: TaskRequest,
    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user.id

    try:

        result = create_task(
            document_id=request.document_id,
            title=request.title,
            user_id=user_id,
        )

        if not result:

            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )

        return {
            "success": True,
            "task": result,
        }

    except HTTPException:

        raise

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Failed to create task",
        )


# =========================================================
# GET DOCUMENT TASKS
# =========================================================

@router.get(
    "/tasks/{document_id}"
)
async def list_tasks(
    document_id: str,
    current_user=Depends(
        get_current_user
    ),
):

    user_id = current_user.id

    try:

        return get_tasks(
            document_id=document_id,
            user_id=user_id,
        )

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Failed to load tasks",
        )