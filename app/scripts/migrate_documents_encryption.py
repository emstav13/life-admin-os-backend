import json
import sys

from app.services.db_service import supabase
from app.services.encryption_service import (
    encrypt_text,
    decrypt_text,
)


# =========================================================
# CONFIGURATION
# =========================================================

TABLE_NAME = "documents"

# IMPORTANT:
# First run with True.
# Nothing will be written to Supabase.
DRY_RUN = False


# =========================================================
# LOAD DOCUMENTS
# =========================================================

def get_documents():

    response = (
        supabase
        .table(TABLE_NAME)
        .select(
            "id, filename, raw_text, summary, ai_json"
        )
        .execute()
    )

    return response.data or []


# =========================================================
# MIGRATE ONE VALUE
# =========================================================

def migrate_value(
    value,
    field_name,
    document_id,
):
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    # -----------------------------------------------------
    # Already AES
    # -----------------------------------------------------

    if value.startswith("aes:v1:"):

        print(
            f"  {field_name}: already AES"
        )

        # Verify that AES can decrypt it.

        decrypted = decrypt_text(
            value
        )

        if decrypted is None:
            raise RuntimeError(
                f"{field_name} AES verification failed "
                f"for document {document_id}"
            )

        return value

    # -----------------------------------------------------
    # Existing Fernet
    # -----------------------------------------------------

    print(
        f"  {field_name}: Fernet → AES"
    )

    try:

        plaintext = decrypt_text(
            value
        )

    except Exception as error:

        raise RuntimeError(
            f"Unable to decrypt existing "
            f"{field_name} for document "
            f"{document_id}"
        ) from error

    if plaintext is None:
        return None

    # -----------------------------------------------------
    # Encrypt using new AES-256-GCM
    # -----------------------------------------------------

    encrypted = encrypt_text(
        plaintext
    )

    # -----------------------------------------------------
    # Verify AES immediately
    # -----------------------------------------------------

    verification = decrypt_text(
        encrypted
    )

    if verification != plaintext:

        raise RuntimeError(
            f"{field_name} AES verification failed "
            f"for document {document_id}"
        )

    return encrypted


# =========================================================
# MIGRATE ONE DOCUMENT
# =========================================================

def migrate_document(document):

    document_id = document["id"]

    filename = (
        document.get(
            "filename"
        )
        or "Unknown"
    )

    print(
        "\n========================================"
    )

    print(
        f"Document: {filename}"
    )

    print(
        f"ID: {document_id}"
    )

    print(
        "========================================"
    )

    # =====================================================
    # RAW TEXT
    # =====================================================

    current_raw_text = (
        document.get(
            "raw_text"
        )
    )

    migrated_raw_text = migrate_value(
        current_raw_text,
        "raw_text",
        document_id,
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    current_summary = (
        document.get(
            "summary"
        )
    )

    migrated_summary = migrate_value(
        current_summary,
        "summary",
        document_id,
    )

    # =====================================================
    # AI JSON
    # =====================================================

    current_ai_json = (
        document.get(
            "ai_json"
        )
    )

    migrated_ai_json = None

    if current_ai_json is not None:

        # -------------------------------------------------
        # Supabase JSONB may return:
        #
        # string
        # dict
        # -------------------------------------------------

        if isinstance(
            current_ai_json,
            dict,
        ):

            # If it is a dict, it is plaintext JSON.

            ai_json_string = json.dumps(
                current_ai_json,
                ensure_ascii=False,
            )

            migrated_ai_json = encrypt_text(
                ai_json_string
            )

            # Verify.

            decrypted_ai_json = decrypt_text(
                migrated_ai_json
            )

            parsed_ai_json = json.loads(
                decrypted_ai_json
            )

            if (
                parsed_ai_json
                != current_ai_json
            ):

                raise RuntimeError(
                    "AI JSON verification failed "
                    f"for document {document_id}"
                )

        else:

            migrated_ai_json = migrate_value(
                str(current_ai_json),
                "ai_json",
                document_id,
            )

            # Make sure encrypted AI JSON
            # contains valid JSON.

            decrypted_ai_json = decrypt_text(
                migrated_ai_json
            )

            json.loads(
                decrypted_ai_json
            )

    # =====================================================
    # BUILD UPDATE
    # =====================================================

    update_data = {
        "raw_text":
            migrated_raw_text,

        "summary":
            migrated_summary,

        "ai_json":
            migrated_ai_json,
    }

    # =====================================================
    # DRY RUN
    # =====================================================

    if DRY_RUN:

        print(
            "\n🟡 DRY RUN"
        )

        print(
            "No database changes were made."
        )

        return

    # =====================================================
    # WRITE TO DATABASE
    # =====================================================

    print(
        "\nWriting AES encrypted values "
        "to database..."
    )

    response = (
        supabase
        .table(TABLE_NAME)
        .update(update_data)
        .eq(
            "id",
            document_id,
        )
        .execute()
    )

    if not response.data:

        raise RuntimeError(
            "Database update failed "
            f"for document {document_id}"
        )

    # =====================================================
    # FINAL DATABASE VERIFICATION
    # =====================================================

    verification_response = (
        supabase
        .table(TABLE_NAME)
        .select(
            "raw_text, summary, ai_json"
        )
        .eq(
            "id",
            document_id,
        )
        .single()
        .execute()
    )

    saved = (
        verification_response.data
    )

    if not saved:

        raise RuntimeError(
            "Could not verify saved document "
            f"{document_id}"
        )

    # =====================================================
    # VERIFY RAW TEXT
    # =====================================================

    saved_raw_text = (
        saved.get(
            "raw_text"
        )
    )

    if saved_raw_text:

        if not str(
            saved_raw_text
        ).startswith(
            "aes:v1:"
        ):

            raise RuntimeError(
                "FINAL RAW TEXT IS NOT AES "
                f"for document {document_id}"
            )

        decrypt_text(
            saved_raw_text
        )

    # =====================================================
    # VERIFY SUMMARY
    # =====================================================

    saved_summary = (
        saved.get(
            "summary"
        )
    )

    if saved_summary:

        if not str(
            saved_summary
        ).startswith(
            "aes:v1:"
        ):

            raise RuntimeError(
                "FINAL SUMMARY IS NOT AES "
                f"for document {document_id}"
            )

        decrypt_text(
            saved_summary
        )

    # =====================================================
    # VERIFY AI JSON
    # =====================================================

    saved_ai_json = (
        saved.get(
            "ai_json"
        )
    )

    if saved_ai_json:

        if not isinstance(
            saved_ai_json,
            str,
        ):

            raise RuntimeError(
                "FINAL AI JSON IS NOT A STRING "
                f"for document {document_id}"
            )

        if not saved_ai_json.startswith(
            "aes:v1:"
        ):

            raise RuntimeError(
                "FINAL AI JSON IS NOT AES "
                f"for document {document_id}"
            )

        decrypted_ai_json = decrypt_text(
            saved_ai_json
        )

        json.loads(
            decrypted_ai_json
        )

    print(
        "✅ AES + database verification: OK"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "\n========================================"
    )

    print(
        "LIFE AiOS"
    )

    print(
        "FERNET → AES-256-GCM MIGRATION"
    )

    print(
        "========================================\n"
    )

    print(
        f"DRY_RUN = {DRY_RUN}"
    )

    documents = get_documents()

    print(
        f"Documents found: {len(documents)}"
    )

    if not documents:

        print(
            "No documents found."
        )

        return

    successful = 0

    for document in documents:

        try:

            migrate_document(
                document
            )

            successful += 1

        except Exception as error:

            print(
                "\n❌ MIGRATION FAILED"
            )

            print(
                "Document:",
                document.get(
                    "id"
                ),
            )

            print(
                "Error:",
                error,
            )

            print(
                "\nMigration stopped."
            )

            sys.exit(1)

    print(
        "\n========================================"
    )

    print(
        "DRY RUN COMPLETE"
        if DRY_RUN
        else "MIGRATION COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        f"Successfully processed: "
        f"{successful}/{len(documents)}"
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()