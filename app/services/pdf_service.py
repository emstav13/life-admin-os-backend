import fitz


# =========================================================
# SECURITY LIMITS
# =========================================================

MAX_PDF_PAGES = 100
MAX_EXTRACTED_TEXT = 500_000


# =========================================================
# PDF TEXT EXTRACTION
# =========================================================

def extract_text_from_pdf(
    file_bytes: bytes,
) -> str:

    if not file_bytes:
        raise ValueError(
            "PDF file is empty"
        )

    if not file_bytes.startswith(
        b"%PDF"
    ):
        raise ValueError(
            "Invalid PDF signature"
        )

    pdf = None

    try:

        pdf = fitz.open(
            stream=file_bytes,
            filetype="pdf",
        )

        # -------------------------------------------------
        # PAGE LIMIT
        # -------------------------------------------------

        if pdf.page_count > MAX_PDF_PAGES:

            raise ValueError(
                "PDF contains too many pages"
            )

        text_parts = []

        total_length = 0

        # -------------------------------------------------
        # EXTRACT TEXT
        # -------------------------------------------------

        for page in pdf:

            page_text = (
                page.get_text()
                or ""
            )

            if not page_text:
                continue

            remaining = (
                MAX_EXTRACTED_TEXT
                - total_length
            )

            if remaining <= 0:
                break

            page_text = page_text[
                :remaining
            ]

            text_parts.append(
                page_text
            )

            total_length += len(
                page_text
            )

            if total_length >= MAX_EXTRACTED_TEXT:
                break

        return "\n".join(
            text_parts
        )

    except ValueError:
        raise

    except Exception as error:

        raise ValueError(
            "Unable to parse PDF"
        ) from error

    finally:

        if pdf is not None:

            pdf.close()