import os
import json

from openai import OpenAI
from dotenv import load_dotenv

from app.services.ai_privacy import (
    sanitize_for_ai,
    sanitize_question,
    sanitize_ai_metadata,
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is not configured"
    )


# =========================================================
# OPENAI CLIENT
# =========================================================

client = OpenAI(
    api_key=OPENAI_API_KEY
)


# =========================================================
# CONFIGURATION
# =========================================================

DOCUMENT_EXTRACTION_LIMIT = 12000

DOCUMENT_QUESTION_LIMIT = 15000

DOCUMENT_ACTIONS_LIMIT = 15000

DOCUMENT_TASKS_LIMIT = 15000

DAILY_BRIEFING_DOCUMENT_LIMIT = 8000

MAX_BRIEFING_DOCUMENTS = 20


# =========================================================
# HELPER
# =========================================================

def clean_text(
    text: str | None,
    max_length: int,
) -> str:
    """
    Clean and limit text before AI processing.
    """

    if not text:
        return ""

    if not isinstance(
        text,
        str
    ):
        text = str(text)

    return text.strip()[:max_length]


# =========================================================
# EXTRACT DOCUMENT DATA
# =========================================================

def extract_document_data(
    text: str,
):
    safe_text = clean_text(
        sanitize_for_ai(text),
        DOCUMENT_EXTRACTION_LIMIT,
    )

    if not safe_text:
        raise ValueError(
            "Document contains no usable text"
        )

    response = (
        client.chat.completions.create(

            model="gpt-4.1-mini",

            # Do not store the Chat Completion.
            store=False,

            response_format={
                "type": "json_object"
            },

            messages=[
                {
                    "role": "system",

                    "content": """
You are a document extraction AI.

Your purpose is to extract only the
information necessary to organize
a user's document.

Do not invent information.

Return ONLY valid JSON.
""",
                },

                {
                    "role": "user",

                    "content": f"""
Analyze this document.

Return JSON with:

- document_type
- provider
- amount
- due_date
- urgency
- short_summary

Rules:

- Always return all fields.
- If provider is missing return null.
- If amount is missing return null.
- If due_date is missing return null.
- urgency must be high, medium, or low.
- short_summary maximum 100 words.
- Return ONLY valid JSON.

Document:

{safe_text}
""",
                },
            ],

            temperature=0,
        )
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:
        raise ValueError(
            "OpenAI returned an empty response"
        )

    return json.loads(
        content
    )


# =========================================================
# ASK QUESTION ABOUT ONE DOCUMENT
# =========================================================

def ask_document_question(
    document_text: str,
    question: str,
):

    safe_document_text = clean_text(
        sanitize_for_ai(document_text),
        DOCUMENT_QUESTION_LIMIT,
    )

    safe_question = sanitize_question(
        question,
        2000,
    )

    if not safe_document_text:
        raise ValueError(
            "Document contains no usable text"
        )

    if not safe_question:
        raise ValueError(
            "Question is empty"
        )

    response = (
        client.chat.completions.create(

            model="gpt-4.1-mini",

            # Do not store the Chat Completion.
            store=False,

            messages=[
                {
                    "role": "system",

                    "content": """
You answer questions about a document.

Only use information found in the
provided document.

Do not invent facts.

If the answer is not found,
clearly say so.
""",
                },

                {
                    "role": "user",

                    "content": f"""
Document:

{safe_document_text}

Question:

{safe_question}
""",
                },
            ],

            temperature=0,
        )
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    return content or ""


# =========================================================
# GENERATE DOCUMENT ACTIONS
# =========================================================

def generate_document_actions(
    text: str,
):

    safe_text = clean_text(
        sanitize_for_ai(text),
        DOCUMENT_ACTIONS_LIMIT,
    )

    if not safe_text:
        return ""

    response = (
        client.chat.completions.create(

            model="gpt-4.1-mini",

            # Do not store the Chat Completion.
            store=False,

            messages=[
                {
                    "role": "system",

                    "content": """
Analyze the document.

Return a short list of actions
the user should take.

Maximum 5 actions.

Use bullet points.

Do not invent actions that are
not supported by the document.
""",
                },

                {
                    "role": "user",

                    "content": safe_text,
                },
            ],

            temperature=0,
        )
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    return content or ""


# =========================================================
# EXTRACT TASK LIST
# =========================================================

def extract_action_list(
    text: str,
):

    safe_text = clean_text(
        sanitize_for_ai(text),
        DOCUMENT_TASKS_LIMIT,
    )

    if not safe_text:
        return {
            "tasks": []
        }

    response = (
        client.chat.completions.create(

            model="gpt-4.1-mini",

            # Do not store the Chat Completion.
            store=False,

            response_format={
                "type": "json_object"
            },

            messages=[
                {
                    "role": "system",

                    "content": """
Return valid JSON.

Format:

{
  "tasks": [
    "task 1",
    "task 2"
  ]
}

Maximum 5 tasks.

Do not invent tasks.

Only create tasks supported
by the document.
""",
                },

                {
                    "role": "user",

                    "content": safe_text,
                },
            ],

            temperature=0,
        )
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:
        return {
            "tasks": []
        }

    result = json.loads(
        content
    )

    if not isinstance(
        result,
        dict,
    ):
        return {
            "tasks": []
        }

    tasks = result.get(
        "tasks",
        []
    )

    if not isinstance(
        tasks,
        list,
    ):
        return {
            "tasks": []
        }

    result["tasks"] = [
        task.strip()
        for task in tasks[:5]
        if isinstance(
            task,
            str,
        )
        and task.strip()
    ]

    return result


# =========================================================
# DAILY BRIEFING
# =========================================================

def generate_daily_briefing(
    documents,
):
    """
    Generate a concise, structured Daily Briefing.

    Only selected document metadata is sent to OpenAI.

    raw_text and user_id are intentionally excluded.
    """

    # -----------------------------------------------------
    # NORMALIZE INPUT
    # -----------------------------------------------------

    if not isinstance(
        documents,
        list,
    ):
        return ""

    document_count = len(
        documents
    )

    # Never log document contents.
    print(
        "DAILY_BRIEFING_DOCUMENT_COUNT:",
        document_count,
    )

    if document_count == 0:
        return ""

    # -----------------------------------------------------
    # BUILD SAFE DOCUMENT METADATA
    # -----------------------------------------------------

    briefing_documents = []

    for document in documents[
        :MAX_BRIEFING_DOCUMENTS
    ]:

        if not isinstance(
            document,
            dict,
        ):
            continue

        ai_json = (
            document.get(
                "ai_json",
                {},
            )
            or {}
        )

        if not isinstance(
            ai_json,
            dict,
        ):
            ai_json = {}

        # -------------------------------------------------
        # SUMMARY
        # -------------------------------------------------

        summary = document.get(
            "summary",
        )

        if not summary:
            summary = ai_json.get(
                "short_summary",
            )

        # -------------------------------------------------
        # SAFE METADATA
        #
        # IMPORTANT:
        # raw_text and user_id are NOT included.
        # -------------------------------------------------

        briefing_documents.append(
            {
                "filename": clean_text(
                    document.get(
                        "filename",
                        "Document",
                    ),
                    300,
                ),

                "document_type": clean_text(
                    document.get(
                        "document_type",
                    ),
                    200,
                ),

                "summary": clean_text(
                    summary,
                    DAILY_BRIEFING_DOCUMENT_LIMIT,
                ),

                "provider": clean_text(
                    ai_json.get(
                        "provider",
                    ),
                    300,
                ),

                "amount": clean_text(
                    ai_json.get(
                        "amount",
                    ),
                    100,
                ),

                "due_date": clean_text(
                    ai_json.get(
                        "due_date",
                    ),
                    100,
                ),

                "urgency": clean_text(
                    ai_json.get(
                        "urgency",
                    ),
                    50,
                ),

                "actions": ai_json.get(
                    "actions",
                ),
            }
        )

    # -----------------------------------------------------
    # SANITIZE EACH DOCUMENT INDIVIDUALLY
    # -----------------------------------------------------

    safe_documents_data = [
        sanitize_ai_metadata(
            document
        )
        for document in briefing_documents
    ]

    # -----------------------------------------------------
    # SAFE JSON
    # -----------------------------------------------------

    safe_documents = json.dumps(
        safe_documents_data,
        ensure_ascii=False,
    )

    print(
        "DAILY_BRIEFING_AI_DOCUMENT_COUNT:",
        len(
            briefing_documents
        ),
    )

    # -----------------------------------------------------
    # OPENAI REQUEST
    # -----------------------------------------------------

    try:

        response = (
            client.chat.completions.create(

                model="gpt-4.1-mini",

                # Do not store the Chat Completion.
                store=False,

                messages=[
                    {
                        "role": "system",

                        "content": """
You are the Daily Briefing assistant
for Life AiOS.

Your job is to organize the user's
document information into a concise,
clean and premium-looking briefing.

The backend has already loaded the
user's documents.

The DOCUMENT_COUNT value is authoritative.

If DOCUMENT_COUNT is greater than 0,
documents exist.

========================================================
IMPORTANT DATA RULES
========================================================

Use ONLY the supplied document metadata.

Never invent:

- names
- dates
- amounts
- providers
- priorities
- deadlines
- actions
- summaries
- financial obligations

If a field does not exist, omit it.

Do not infer that an identified amount
is a payment or debt unless the metadata
explicitly supports that interpretation.

For financial information, use neutral
language such as:

"Amount identified: €200"

when the document does not explicitly
state that the amount is a payment.

========================================================
FORBIDDEN GENERIC TEXT
========================================================

Do NOT write generic filler such as:

- "Stay organized."
- "Stay informed."
- "Keep an eye on your documents."
- "Review your documents when convenient."
- "Take some time to review your documents."
- "No action is required at this time."
- "You should stay prepared."

Every sentence must provide useful
information based on the documents.

========================================================
FORBIDDEN DOCUMENT RESPONSES
========================================================

If DOCUMENT_COUNT is greater than 0,
NEVER say:

- "No documents were provided."
- "No documents were found."
- "There are no documents."
- "Please provide documents."

========================================================
EXACT RESPONSE STRUCTURE
========================================================

Return ONLY these sections,
in this exact order.

Do NOT create any other sections.

--------------------------------------------------------
🧠 DAILY OVERVIEW
--------------------------------------------------------

Write a short overview of the actual
documents.

Mention the most important information
when available.

Keep this to approximately 1-3 sentences.

--------------------------------------------------------
📄 DOCUMENTS
--------------------------------------------------------

List each relevant document individually.

For each document show ONLY available
information.

Use this style:

• Document name
  Provider: ...
  Amount: ...
  Due: ...
  Priority: ...
  Details: ...

Do NOT display empty fields.

Keep Details concise and factual.

--------------------------------------------------------
🔴 HIGH PRIORITY
--------------------------------------------------------

Include ONLY documents where:

urgency = high

For each one provide:

• Document name
  Reason: ...

The reason must be based on the actual
metadata.

If there are no high-priority documents,
omit this entire section.

--------------------------------------------------------
📅 UPCOMING DEADLINES
--------------------------------------------------------

Include documents that contain
a due date.

Use:

• Document name
  Due: ...

If there are no due dates,
omit this entire section.

--------------------------------------------------------
💰 PAYMENTS & FINANCIAL ITEMS
--------------------------------------------------------

Include documents where an amount
is actually available.

Use:

• Document name
  Amount identified: ...

Add the due date when available.

IMPORTANT:

Do not call an amount a "payment",
"debt", "fee", or "obligation" unless
the metadata explicitly supports that.

If no amounts exist,
omit this entire section.

========================================================
STYLE
========================================================

- Professional.
- Clean.
- Concise.
- Easy to scan.
- Premium SaaS style.
- Use bullets.
- Use short paragraphs.
- Use blank lines between sections.
- Do not use markdown tables.
- Do not add an introduction before
  🧠 DAILY OVERVIEW.
- Do not add a conclusion.
- Do not add recommendations.
- Do not add an "Actions" section.
- Do not add an "AI Insights" section.
- Do not add any section that was not
  explicitly requested above.

The briefing should normally be around
150-250 words when enough information
exists.

If there is little information,
make it shorter.

Return ONLY the Daily Briefing.
""",
                    },

                    {
                        "role": "user",

                        "content": f"""
DOCUMENT_COUNT:
{document_count}

DOCUMENTS:
{safe_documents}
""",
                    },
                ],

                temperature=0,
            )
        )

    except Exception:
        return _build_daily_briefing_fallback(
            briefing_documents,
            document_count,
        )

    # -----------------------------------------------------
    # EXTRACT RESPONSE
    # -----------------------------------------------------

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:
        return _build_daily_briefing_fallback(
            briefing_documents,
            document_count,
        )

    content = content.strip()

    # -----------------------------------------------------
    # PROTECT AGAINST INCORRECT RESPONSE
    # -----------------------------------------------------

    forbidden_no_document_phrases = (
        "no documents were provided",
        "no documents were found",
        "there are no documents",
        "please provide documents",
    )

    normalized_content = (
        content.lower()
    )

    if any(
        phrase in normalized_content
        for phrase in forbidden_no_document_phrases
    ):
        return _build_daily_briefing_fallback(
            briefing_documents,
            document_count,
        )

    return content


# =========================================================
# DAILY BRIEFING FALLBACK
# =========================================================

def _build_daily_briefing_fallback(
    briefing_documents,
    document_count,
):
    """
    Deterministic fallback.

    Uses only already-selected metadata.
    """

    if document_count <= 0:
        return ""

    sections = []

    # -----------------------------------------------------
    # OVERVIEW
    # -----------------------------------------------------

    sections.append(
        "🧠 DAILY OVERVIEW\n\n"
        f"You have {document_count} "
        "document(s) available for review."
    )

    # -----------------------------------------------------
    # DOCUMENTS
    # -----------------------------------------------------

    document_lines = []

    for item in briefing_documents:

        if not isinstance(
            item,
            dict,
        ):
            continue

        filename = item.get(
            "filename",
            "Document",
        )

        lines = [
            f"• {filename}"
        ]

        document_type = item.get(
            "document_type",
        )

        provider = item.get(
            "provider",
        )

        amount = item.get(
            "amount",
        )

        due_date = item.get(
            "due_date",
        )

        urgency = item.get(
            "urgency",
        )

        summary = item.get(
            "summary",
        )

        if provider:
            lines.append(
                f"  Provider: {provider}"
            )

        if amount:
            lines.append(
                f"  Amount: {amount}"
            )

        if due_date:
            lines.append(
                f"  Due: {due_date}"
            )

        if urgency:
            lines.append(
                f"  Priority: {urgency.title()}"
            )

        if summary:
            lines.append(
                f"  Details: {summary}"
            )

        if document_type and not summary:
            lines.append(
                f"  Type: {document_type}"
            )

        document_lines.append(
            "\n".join(lines)
        )

    if document_lines:

        sections.append(
            "📄 DOCUMENTS\n\n"
            + "\n\n".join(
                document_lines
            )
        )

    # -----------------------------------------------------
    # HIGH PRIORITY
    # -----------------------------------------------------

    high_priority_lines = []

    for item in briefing_documents:

        if not isinstance(
            item,
            dict,
        ):
            continue

        urgency = str(
            item.get(
                "urgency",
                "",
            )
        ).lower()

        if urgency != "high":
            continue

        filename = item.get(
            "filename",
            "Document",
        )

        reason_parts = []

        if item.get(
            "due_date"
        ):
            reason_parts.append(
                f"due {item['due_date']}"
            )

        if item.get(
            "amount"
        ):
            reason_parts.append(
                f"amount identified: "
                f"{item['amount']}"
            )

        if reason_parts:
            reason = "; ".join(
                reason_parts
            )
        else:
            reason = (
                "High priority status "
                "identified in the document metadata."
            )

        high_priority_lines.append(
            f"• {filename}\n"
            f"  Reason: {reason}"
        )

    if high_priority_lines:

        sections.append(
            "🔴 HIGH PRIORITY\n\n"
            + "\n\n".join(
                high_priority_lines
            )
        )

    # -----------------------------------------------------
    # UPCOMING DEADLINES
    # -----------------------------------------------------

    deadline_lines = []

    for item in briefing_documents:

        if not isinstance(
            item,
            dict,
        ):
            continue

        due_date = item.get(
            "due_date"
        )

        if not due_date:
            continue

        filename = item.get(
            "filename",
            "Document",
        )

        deadline_lines.append(
            f"• {filename}\n"
            f"  Due: {due_date}"
        )

    if deadline_lines:

        sections.append(
            "📅 UPCOMING DEADLINES\n\n"
            + "\n\n".join(
                deadline_lines
            )
        )

    # -----------------------------------------------------
    # FINANCIAL ITEMS
    # -----------------------------------------------------

    financial_lines = []

    for item in briefing_documents:

        if not isinstance(
            item,
            dict,
        ):
            continue

        amount = item.get(
            "amount"
        )

        if not amount:
            continue

        filename = item.get(
            "filename",
            "Document",
        )

        line = (
            f"• {filename}\n"
            f"  Amount identified: {amount}"
        )

        if item.get(
            "due_date"
        ):
            line += (
                f"\n  Due: "
                f"{item['due_date']}"
            )

        financial_lines.append(
            line
        )

    if financial_lines:

        sections.append(
            "💰 PAYMENTS & FINANCIAL ITEMS\n\n"
            + "\n\n".join(
                financial_lines
            )
        )

    return "\n\n────────────────────────\n\n".join(
        sections
    )