import re
from typing import Any


# =========================================================
# AI PRIVACY / DATA SANITIZATION
# =========================================================
#
# This module contains ONLY privacy sanitization helpers.
#
# IMPORTANT:
# - No OpenAI client
# - No database access
# - No imports from ai_service
# - No imports from ai_privacy itself
#
# The goal is to minimize sensitive personal data before
# document content is sent to an external AI provider.
# =========================================================


# =========================================================
# REGEX PATTERNS
# =========================================================

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)


PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+?\d{1,3}[\s.-]?)?"
    r"(?:\(?\d{2,4}\)?[\s.-]?)?"
    r"\d{3,4}[\s.-]?\d{3,4}"
    r"(?!\d)"
)


IBAN_PATTERN = re.compile(
    r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
    re.IGNORECASE,
)


CREDIT_CARD_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\d[ -]?){13,19}"
    r"(?!\d)"
)


AFM_PATTERN = re.compile(
    r"(?i)"
    r"\b(?:AFM|ΑΦΜ)"
    r"\s*[:\-]?\s*\d{9}\b"
)


AMKA_PATTERN = re.compile(
    r"(?i)"
    r"\b(?:AMKA|ΑΜΚΑ)"
    r"\s*[:\-]?\s*\d{11}\b"
)


PASSPORT_PATTERN = re.compile(
    r"(?i)"
    r"\b(?:passport|διαβατήριο)"
    r"\s*(?:no|number|αρ|αριθμός)?"
    r"\s*[:\-]?\s*[A-Z0-9]{6,12}\b"
)


ID_PATTERN = re.compile(
    r"(?i)"
    r"\b(?:"
    r"id|identity|identity\s+card|"
    r"ταυτότητα|ταυτοτητα|"
    r"αριθμός\s+ταυτότητας|"
    r"αριθμος\s+ταυτοτητας"
    r")"
    r"\s*(?:no|number|αρ|αριθμός)?"
    r"\s*[:\-]?\s*[A-Z0-9]{5,15}\b"
)


BANK_ACCOUNT_PATTERN = re.compile(
    r"(?i)"
    r"\b(?:"
    r"account|account\s+number|"
    r"bank\s+account|"
    r"λογαριασμός|"
    r"λογαριασμου"
    r")"
    r"\s*(?:no|number|αρ|αριθμός)?"
    r"\s*[:\-]?\s*\d{6,24}\b"
)


# =========================================================
# URL PATTERN
# =========================================================

URL_PATTERN = re.compile(
    r"\bhttps?://[^\s<>\"]+",
    re.IGNORECASE,
)


# =========================================================
# ADDRESS PATTERNS
# =========================================================

ADDRESS_PATTERN = re.compile(
    r"(?im)"
    r"\b(?:"
    r"address|"
    r"home\s+address|"
    r"residential\s+address|"
    r"διεύθυνση|"
    r"διευθυνση|"
    r"οδός|"
    r"οδος"
    r")"
    r"\s*[:\-]\s*"
    r"[^\n]{5,150}"
)


# =========================================================
# NAME-LIKE LABELS
# =========================================================

PERSONAL_NAME_PATTERN = re.compile(
    r"(?im)"
    r"\b(?:"
    r"full\s+name|"
    r"first\s+name|"
    r"last\s+name|"
    r"ονοματεπώνυμο|"
    r"ονοματεπωνυμο|"
    r"όνομα|"
    r"ονομα|"
    r"επώνυμο|"
    r"επωνυμο"
    r")"
    r"\s*[:\-]\s*"
    r"[^\n]{2,100}"
)


# =========================================================
# SANITIZATION HELPERS
# =========================================================

def _replace(
    pattern: re.Pattern,
    text: str,
    replacement: str,
) -> str:

    return pattern.sub(
        replacement,
        text,
    )


# =========================================================
# SANITIZE DOCUMENT TEXT
# =========================================================

def sanitize_for_ai(
    text: Any,
) -> str:
    """
    Remove or redact common sensitive personal data
    before text is sent to an external AI provider.

    The function intentionally keeps normal document content
    so the AI can still understand the document.
    """

    if text is None:
        return ""

    if not isinstance(text, str):
        text = str(text)

    sanitized = text

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    sanitized = _replace(
        EMAIL_PATTERN,
        sanitized,
        "[EMAIL_REDACTED]",
    )

    # -----------------------------------------------------
    # IBAN
    # -----------------------------------------------------

    sanitized = _replace(
        IBAN_PATTERN,
        sanitized,
        "[IBAN_REDACTED]",
    )

    # -----------------------------------------------------
    # CREDIT / PAYMENT CARD
    # -----------------------------------------------------

    sanitized = _replace(
        CREDIT_CARD_PATTERN,
        sanitized,
        "[CARD_REDACTED]",
    )

    # -----------------------------------------------------
    # AFM
    # -----------------------------------------------------

    sanitized = _replace(
        AFM_PATTERN,
        sanitized,
        "[AFM_REDACTED]",
    )

    # -----------------------------------------------------
    # AMKA
    # -----------------------------------------------------

    sanitized = _replace(
        AMKA_PATTERN,
        sanitized,
        "[AMKA_REDACTED]",
    )

    # -----------------------------------------------------
    # PASSPORT
    # -----------------------------------------------------

    sanitized = _replace(
        PASSPORT_PATTERN,
        sanitized,
        "[PASSPORT_REDACTED]",
    )

    # -----------------------------------------------------
    # IDENTITY NUMBER
    # -----------------------------------------------------

    sanitized = _replace(
        ID_PATTERN,
        sanitized,
        "[ID_REDACTED]",
    )

    # -----------------------------------------------------
    # BANK ACCOUNT
    # -----------------------------------------------------

    sanitized = _replace(
        BANK_ACCOUNT_PATTERN,
        sanitized,
        "[BANK_ACCOUNT_REDACTED]",
    )

    # -----------------------------------------------------
    # URL
    # -----------------------------------------------------

    sanitized = _replace(
        URL_PATTERN,
        sanitized,
        "[URL_REDACTED]",
    )

    # -----------------------------------------------------
    # ADDRESS
    # -----------------------------------------------------

    sanitized = _replace(
        ADDRESS_PATTERN,
        sanitized,
        "[ADDRESS_REDACTED]",
    )

    # -----------------------------------------------------
    # PHONE
    # -----------------------------------------------------

    sanitized = _replace(
        PHONE_PATTERN,
        sanitized,
        "[PHONE_REDACTED]",
    )

    # -----------------------------------------------------
    # LABELED PERSONAL NAME
    # -----------------------------------------------------

    sanitized = _replace(
        PERSONAL_NAME_PATTERN,
        sanitized,
        "[PERSONAL_NAME_REDACTED]",
    )

    return sanitized


# =========================================================
# SANITIZE AI QUESTION
# =========================================================

def sanitize_question(
    question: Any,
) -> str:
    """
    Sanitize a user question before sending it to AI.

    Limits size to prevent unnecessarily large requests.
    """

    if question is None:
        return ""

    if not isinstance(question, str):
        question = str(question)

    question = question.strip()

    if not question:
        return ""

    # -----------------------------------------------------
    # LIMIT REQUEST SIZE
    # -----------------------------------------------------

    question = question[:4000]

    return sanitize_for_ai(
        question
    )


# =========================================================
# SANITIZE AI METADATA
# =========================================================

def sanitize_ai_metadata(
    metadata: Any,
) -> dict:
    """
    Sanitize metadata before it is included in an AI prompt.

    Only primitive values are retained.
    """

    if not isinstance(
        metadata,
        dict,
    ):
        return {}

    safe_metadata = {}

    allowed_keys = {
        "provider",
        "amount",
        "due_date",
        "urgency",
        "priority",
        "document_type",
        "short_summary",
        "summary",
        "filename",
    }

    for key, value in metadata.items():

        if key not in allowed_keys:
            continue

        if value is None:
            continue

        if isinstance(
            value,
            (str, int, float, bool),
        ):

            if isinstance(
                value,
                str,
            ):

                value = sanitize_for_ai(
                    value
                )[:2000]

            safe_metadata[key] = value

    return safe_metadata


# =========================================================
# SANITIZE DOCUMENT METADATA COLLECTION
# =========================================================

def sanitize_documents_for_ai(
    documents: Any,
) -> list[dict]:
    """
    Sanitize a collection of document dictionaries.

    Useful for multi-document AI requests.
    """

    if not isinstance(
        documents,
        list,
    ):
        return []

    result = []

    for document in documents:

        if not isinstance(
            document,
            dict,
        ):
            continue

        safe_document = {}

        filename = document.get(
            "filename"
        )

        if filename:
            safe_document["filename"] = (
                sanitize_for_ai(
                    filename
                )[:500]
            )

        document_type = document.get(
            "document_type"
        )

        if document_type:
            safe_document["document_type"] = (
                sanitize_for_ai(
                    document_type
                )[:200]
            )

        summary = document.get(
            "summary"
        )

        if summary:
            safe_document["summary"] = (
                sanitize_for_ai(
                    summary
                )[:5000]
            )

        raw_text = document.get(
            "raw_text"
        )

        if raw_text:
            safe_document["raw_text"] = (
                sanitize_for_ai(
                    raw_text
                )
            )

        ai_json = document.get(
            "ai_json"
        )

        if isinstance(
            ai_json,
            dict,
        ):
            safe_document["ai_json"] = (
                sanitize_ai_metadata(
                    ai_json
                )
            )

        result.append(
            safe_document
        )

    return result