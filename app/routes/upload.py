from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    Depends,
    HTTPException,
    Request,
)

from app.dependencies.auth import (
    get_current_user,
)

from app.services.pdf_service import (
    extract_text_from_pdf,
)

from app.services.ai_service import (
    extract_document_data,
    generate_document_actions,
    extract_action_list,
)

from app.services.db_service import (
    save_document,
    create_task,
    create_reminder,
    check_document_upload_quota,
)

from app.services.rate_limiter import (
    limiter,
)


# =========================================================
# ROUTER
# =========================================================

router = APIRouter()


# =========================================================
# SECURITY CONFIGURATION
# =========================================================

MAX_UPLOAD_SIZE = (
    10 * 1024 * 1024
)

ALLOWED_EXTENSION = ".pdf"

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
}

ALLOWED_PRIORITIES = {
    "high",
    "medium",
    "low",
}

ALLOWED_REPEAT_TYPES = {
    "none",
    "daily",
    "weekly",
    "monthly",
}


# =========================================================
# UPLOAD DOCUMENT
# =========================================================

@router.post("/upload")
@limiter.limit("10/minute")
async def upload_file(
    request: Request,

    file: UploadFile = File(...),

    priority: str = Form(""),

    reminder_enabled: bool = Form(False),

    reminder_date: str = Form(""),

    reminder_time: str = Form(""),

    repeat: str = Form("none"),

    dashboard_notification: bool = Form(True),

    email_notification: bool = Form(True),

    mobile_push: bool = Form(False),

    current_user=Depends(
        get_current_user
    ),
):

    # =====================================================
    # AUTHENTICATED USER
    # =====================================================

    user_id = current_user.id

    # =====================================================
    # SUBSCRIPTION / UPLOAD QUOTA
    # =====================================================

    quota = check_document_upload_quota(
        user_id
    )

    if not quota["allowed"]:

        reason = quota["reason"]

        if reason == "free_limit_reached":

            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FREE_LIMIT_REACHED",
                    "message": (
                        "You have reached the "
                        "5-document Free plan limit."
                    ),
                    "plan": "free",
                    "used": quota["used"],
                    "limit": quota["limit"],
                },
            )

        if reason == "pro_monthly_limit_reached":

            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PRO_MONTHLY_LIMIT_REACHED",
                    "message": (
                        "You have reached the "
                        "20-document monthly Pro limit."
                    ),
                    "plan": "pro",
                    "used": quota["used"],
                    "limit": quota["limit"],
                },
            )

        raise HTTPException(
            status_code=403,
            detail={
                "code": "UPLOAD_NOT_ALLOWED",
                "message": (
                    "Document upload is currently "
                    "not available for this account."
                ),
            },
        )
    # =====================================================
    # FILE NAME VALIDATION
    # =====================================================

    original_filename = (
        file.filename or ""
    ).strip()

    if not original_filename:

        raise HTTPException(
            status_code=400,
            detail="File name is required",
        )


    # -----------------------------------------------------
    # REMOVE PATH COMPONENTS
    # -----------------------------------------------------

    safe_filename = Path(
        original_filename
    ).name


    if not safe_filename:

        raise HTTPException(
            status_code=400,
            detail="Invalid file name",
        )


    # -----------------------------------------------------
    # PDF EXTENSION
    # -----------------------------------------------------

    if not safe_filename.lower().endswith(
        ALLOWED_EXTENSION
    ):

        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )


    original_filename = safe_filename


    # =====================================================
    # CONTENT TYPE VALIDATION
    # =====================================================

    if file.content_type not in (
        ALLOWED_CONTENT_TYPES
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid file type. "
                "Only PDF files are allowed"
            ),
        )


    # =====================================================
    # READ FILE
    # =====================================================

    try:

        file_bytes = await file.read()

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Unable to read uploaded file",
        )


    # =====================================================
    # FILE SIZE LIMIT
    # =====================================================

    if len(file_bytes) == 0:

        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty",
        )


    if len(file_bytes) > MAX_UPLOAD_SIZE:

        raise HTTPException(
            status_code=413,
            detail=(
                "File is too large. "
                "Maximum size is 10 MB"
            ),
        )


    # =====================================================
    # REAL PDF SIGNATURE VALIDATION
    # =====================================================

    if not file_bytes.startswith(
        b"%PDF"
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file",
        )


    # =====================================================
    # PDF TEXT EXTRACTION
    # =====================================================

    try:

        extracted_text = (
            extract_text_from_pdf(
                file_bytes
            )
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Invalid or unsupported PDF file",
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail="Unable to process the PDF",
        )


    # =====================================================
    # READABLE TEXT VALIDATION
    # =====================================================

    if (
        not extracted_text
        or not extracted_text.strip()
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "The PDF does not contain "
                "readable text"
            ),
        )


    # =====================================================
    # AI DOCUMENT ANALYSIS
    # =====================================================

    try:

        ai_result = extract_document_data(
            extracted_text
        )

    except Exception as error:
        print(
            "AI DOCUMENT ANALYSIS ERROR:",
            repr(error),
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to analyze document",
        )

    # =====================================================
    # AI RESULT VALIDATION
    # =====================================================

    if not isinstance(
        ai_result,
        dict,
    ):

        raise HTTPException(
            status_code=500,
            detail="Invalid AI response",
        )


    # =====================================================
    # USER PRIORITY OVERRIDE
    # =====================================================

    normalized_priority = ""

    if priority:

        normalized_priority = (
            priority.strip().lower()
        )

        if (
            normalized_priority
            not in ALLOWED_PRIORITIES
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid priority",
            )

        ai_result["urgency"] = (
            normalized_priority
        )


    # =====================================================
    # VALIDATE REPEAT TYPE
    # =====================================================

    normalized_repeat = (
        repeat.strip().lower()
        if repeat
        else "none"
    )

    if (
        normalized_repeat
        not in ALLOWED_REPEAT_TYPES
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid repeat type",
        )


    # =====================================================
    # GENERATE ACTIONS
    # =====================================================

    try:

        actions = generate_document_actions(
            extracted_text
        )

        if isinstance(
            actions,
            str,
        ):

            ai_result["actions"] = (
                actions
            )

        else:

            ai_result["actions"] = ""


    except Exception:

        ai_result["actions"] = ""


    # =====================================================
    # EXTRACT TASKS
    # =====================================================

    try:

        task_data = extract_action_list(
            extracted_text
        )

    except Exception:

        task_data = {
            "tasks": []
        }


    # =====================================================
    # VALIDATE TASK DATA
    # =====================================================

    if not isinstance(
        task_data,
        dict,
    ):

        task_data = {
            "tasks": []
        }


    tasks = task_data.get(
        "tasks",
        [],
    )


    if not isinstance(
        tasks,
        list,
    ):

        tasks = []


    # =====================================================
    # LIMIT TASK COUNT
    # =====================================================

    tasks = tasks[:5]


    # =====================================================
    # SAVE DOCUMENT
    # =====================================================

    try:

        saved_document = save_document(

            filename=original_filename,

            raw_text=extracted_text,

            ai_data=ai_result,

            # IMPORTANT:
            # user_id comes ONLY from
            # authenticated user.

            user_id=user_id,

            priority=normalized_priority,

            reminder_enabled=(
                reminder_enabled
            ),

            reminder_date=(
                reminder_date
            ),

            reminder_time=(
                reminder_time
            ),

            repeat_type=(
                normalized_repeat
            ),

            dashboard_notification=(
                dashboard_notification
            ),

            email_notification=(
                email_notification
            ),

            mobile_push=(
                mobile_push
            ),
        )

    except Exception:

        raise HTTPException(
            status_code=500,
            detail="Failed to save document",
        )


    # =====================================================
    # VERIFY SAVED DOCUMENT
    # =====================================================

    if not saved_document:

        raise HTTPException(
            status_code=500,
            detail="Failed to save document",
        )


    if not isinstance(
        saved_document,
        dict,
    ):

        raise HTTPException(
            status_code=500,
            detail="Invalid saved document",
        )


    document_id = (
        saved_document.get(
            "id"
        )
    )


    if not document_id:

        raise HTTPException(
            status_code=500,
            detail="Document ID was not generated",
        )


    # =====================================================
    # CREATE REMINDER
    # =====================================================

    if (
        reminder_enabled
        and reminder_date
    ):

        try:

            create_reminder(

                document_id=(
                    document_id
                ),

                user_id=user_id,

                document_name=(
                    original_filename
                ),

                title=(
                    f"Reminder for "
                    f"{original_filename}"
                ),

                message=(
                    f"Reminder for "
                    f"{original_filename} "
                    f"on {reminder_date}"
                ),

                due_date=(
                    reminder_date
                ),

                reminder_time=(
                    reminder_time
                ),

                repeat_type=(
                    normalized_repeat
                ),

                dashboard_notification=(
                    dashboard_notification
                ),

                email_notification=(
                    email_notification
                ),

                mobile_push=(
                    mobile_push
                ),
            )

        except Exception:

            # Do not expose internal
            # reminder errors to the client.

            pass


    # =====================================================
    # CREATE TASKS
    # =====================================================

    for task in tasks:

        if not isinstance(
            task,
            str,
        ):

            continue


        task = task.strip()


        if not task:

            continue


        # -------------------------------------------------
        # LIMIT INDIVIDUAL TASK LENGTH
        # -------------------------------------------------

        if len(task) > 500:

            task = task[:500]


        try:

            # Authenticated user_id
            # is mandatory.
            #
            # create_task() verifies
            # document ownership.

            create_task(

                document_id=(
                    document_id
                ),

                title=task,

                user_id=user_id,
            )

        except Exception:

            # One failed task must not
            # invalidate the document upload.

            continue


    # =====================================================
    # RESPONSE
    # =====================================================

    return {

        "success": True,

        "filename": original_filename,

        "document_id": (
            document_id
        ),

        "data": ai_result,

    }

# =========================================================
# CONVERT FILE TO PDF
# =========================================================

@router.post("/convert-to-pdf")
@limiter.limit("10/minute")
async def convert_to_pdf(
    request: Request,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """
    Convert supported files to PDF.

    Supported:
    - DOCX
    - JPG
    - JPEG
    - PNG
    - WEBP
    - TXT

    Conversion does not consume document quota,
    does not use AI and does not permanently store files.
    """

    import io
    import os
    import shutil
    import subprocess
    import tempfile

    from fastapi.responses import StreamingResponse
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    MAX_SIZE = 10 * 1024 * 1024

    ALLOWED_CONVERSION_EXTENSIONS = {
        ".docx",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".txt",
    }

    # -----------------------------------------------------
    # FILE NAME
    # -----------------------------------------------------

    original_filename = (
        file.filename or ""
    ).strip()

    if not original_filename:
        raise HTTPException(
            status_code=400,
            detail="File name is required",
        )

    safe_filename = Path(
        original_filename
    ).name

    if not safe_filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid file name",
        )

    extension = Path(
        safe_filename
    ).suffix.lower()

    if extension not in ALLOWED_CONVERSION_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Supported formats: DOCX, JPG, JPEG, "
                "PNG, WEBP and TXT."
            ),
        )

    # -----------------------------------------------------
    # READ FILE
    # -----------------------------------------------------

    try:
        file_bytes = await file.read()

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to read uploaded file",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty",
        )

    if len(file_bytes) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "File is too large. "
                "Maximum size is 10 MB."
            ),
        )

    # -----------------------------------------------------
    # TEMPORARY DIRECTORY
    # -----------------------------------------------------

    temp_dir = Path(
        tempfile.mkdtemp(
            prefix="lifeaios_convert_"
        )
    )

    input_path = (
        temp_dir / safe_filename
    )

    output_path = (
        temp_dir
        / f"{Path(safe_filename).stem}.pdf"
    )

    try:

        input_path.write_bytes(
            file_bytes
        )

        # =================================================
        # DOCX → PDF
        # =================================================

        if extension == ".docx":

            libreoffice_path = os.getenv(
                "LIBREOFFICE_PATH",
                r"C:\Program Files\LibreOffice\program\soffice.exe",
            )

            if not Path(
                libreoffice_path
            ).exists():

                raise HTTPException(
                    status_code=500,
                    detail=(
                        "LibreOffice is not available "
                        "for DOCX conversion."
                    ),
                )

            profile_dir = (
                temp_dir / "lo-profile"
            )

            command = [
                libreoffice_path,
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                (
                    f"-env:UserInstallation="
                    f"{profile_dir.resolve().as_uri()}"
                ),
                "--convert-to",
                "pdf",
                "--outdir",
                str(temp_dir),
                str(input_path),
            ]

            try:

                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

            except subprocess.TimeoutExpired:

                raise HTTPException(
                    status_code=504,
                    detail="PDF conversion timed out",
                )

            if (
                result.returncode != 0
                or not output_path.exists()
            ):

                raise HTTPException(
                    status_code=500,
                    detail=(
                        "DOCX to PDF conversion failed."
                    ),
                )

        # =================================================
        # IMAGE → PDF
        # =================================================

        elif extension in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        }:

            try:

                with Image.open(
                    input_path
                ) as source_image:

                    if source_image.mode in {
                        "RGBA",
                        "LA",
                        "P",
                    }:

                        image = Image.new(
                            "RGB",
                            source_image.size,
                            "white",
                        )

                        rgba = (
                            source_image.convert(
                                "RGBA"
                            )
                        )

                        image.paste(
                            rgba,
                            mask=rgba.getchannel(
                                "A"
                            ),
                        )

                    else:

                        image = (
                            source_image.convert(
                                "RGB"
                            )
                        )

                    image.save(
                        output_path,
                        "PDF",
                        resolution=100.0,
                    )

            except Exception:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Unable to convert "
                        "the image to PDF."
                    ),
                )

        # =================================================
        # TXT → PDF
        # =================================================

        elif extension == ".txt":

            try:

                try:
                    text = (
                        file_bytes.decode(
                            "utf-8"
                        )
                    )

                except UnicodeDecodeError:

                    text = (
                        file_bytes.decode(
                            "cp1252"
                        )
                    )

                pdf = canvas.Canvas(
                    str(output_path),
                    pagesize=A4,
                )

                width, height = A4

                left_margin = 50
                right_margin = 50
                top_margin = 50
                bottom_margin = 50

                usable_width = (
                    width
                    - left_margin
                    - right_margin
                )

                font_name = "Helvetica"
                font_size = 10
                line_height = 14

                y = (
                    height
                    - top_margin
                )

                pdf.setFont(
                    font_name,
                    font_size,
                )

                for paragraph in (
                    text.splitlines()
                ):

                    words = paragraph.split()

                    if not words:

                        y -= line_height

                    else:

                        current_line = ""

                        for word in words:

                            candidate = (
                                f"{current_line} "
                                f"{word}"
                            ).strip()

                            if (
                                pdf.stringWidth(
                                    candidate,
                                    font_name,
                                    font_size,
                                )
                                <= usable_width
                            ):

                                current_line = (
                                    candidate
                                )

                            else:

                                if current_line:
                                    pdf.drawString(
                                        left_margin,
                                        y,
                                        current_line,
                                    )

                                    y -= line_height

                                current_line = word

                                if (
                                    y
                                    < bottom_margin
                                ):

                                    pdf.showPage()

                                    pdf.setFont(
                                        font_name,
                                        font_size,
                                    )

                                    y = (
                                        height
                                        - top_margin
                                    )

                        if current_line:

                            pdf.drawString(
                                left_margin,
                                y,
                                current_line,
                            )

                            y -= line_height

                    if (
                        y
                        < bottom_margin
                    ):

                        pdf.showPage()

                        pdf.setFont(
                            font_name,
                            font_size,
                        )

                        y = (
                            height
                            - top_margin
                        )

                pdf.save()

            except Exception:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Unable to convert "
                        "the text file to PDF."
                    ),
                )

        # =================================================
        # VERIFY OUTPUT
        # =================================================

        if not output_path.exists():

            raise HTTPException(
                status_code=500,
                detail=(
                    "PDF file was not generated."
                ),
            )

        pdf_bytes = (
            output_path.read_bytes()
        )

        if not pdf_bytes.startswith(
            b"%PDF"
        ):

            raise HTTPException(
                status_code=500,
                detail=(
                    "Generated file is not "
                    "a valid PDF."
                ),
            )

        # =================================================
        # DOWNLOAD
        # =================================================

        download_name = (
            f"{Path(safe_filename).stem}.pdf"
        )

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; '
                    f'filename="{download_name}"'
                )
            },
        )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to convert file to PDF",
        )

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

