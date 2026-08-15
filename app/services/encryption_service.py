import os
import base64

from cryptography.fernet import (
    Fernet,
    InvalidToken,
)

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from dotenv import load_dotenv


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


# =========================================================
# OLD FERNET KEY
# Used ONLY to decrypt existing data during migration
# =========================================================

DOCUMENT_ENCRYPTION_KEY = os.getenv(
    "DOCUMENT_ENCRYPTION_KEY"
)

if not DOCUMENT_ENCRYPTION_KEY:
    raise RuntimeError(
        "DOCUMENT_ENCRYPTION_KEY is not configured"
    )

try:

    fernet_cipher = Fernet(
        DOCUMENT_ENCRYPTION_KEY.encode()
    )

except Exception as error:

    raise RuntimeError(
        "Invalid DOCUMENT_ENCRYPTION_KEY"
    ) from error


# =========================================================
# NEW AES-256 KEY
# Used for all NEW encryption
# =========================================================

DOCUMENT_ENCRYPTION_AES_KEY = os.getenv(
    "DOCUMENT_ENCRYPTION_AES_KEY"
)

if not DOCUMENT_ENCRYPTION_AES_KEY:
    raise RuntimeError(
        "DOCUMENT_ENCRYPTION_AES_KEY is not configured"
    )

try:

    AES_KEY = base64.urlsafe_b64decode(
        DOCUMENT_ENCRYPTION_AES_KEY.encode()
    )

    if len(AES_KEY) != 32:
        raise ValueError(
            "AES key must contain exactly 32 bytes"
        )

    aes_cipher = AESGCM(AES_KEY)

except Exception as error:

    raise RuntimeError(
        "Invalid DOCUMENT_ENCRYPTION_AES_KEY"
    ) from error


# =========================================================
# CONSTANTS
# =========================================================

AES_PREFIX = "aes:v1:"
AES_NONCE_SIZE = 12


# =========================================================
# ENCRYPT
# =========================================================

def encrypt_text(
    text: str | None,
) -> str | None:

    if text is None:
        return None

    if not isinstance(text, str):
        text = str(text)

    # -----------------------------------------------------
    # AES-256-GCM
    # -----------------------------------------------------

    nonce = os.urandom(
        AES_NONCE_SIZE
    )

    encrypted = aes_cipher.encrypt(
        nonce,
        text.encode("utf-8"),
        None,
    )

    payload = nonce + encrypted

    encoded = base64.urlsafe_b64encode(
        payload
    ).decode("utf-8")

    return AES_PREFIX + encoded


# =========================================================
# DECRYPT
# =========================================================

def decrypt_text(
    encrypted_text: str | None,
) -> str | None:

    if encrypted_text is None:
        return None

    if not isinstance(
        encrypted_text,
        str,
    ):
        encrypted_text = str(
            encrypted_text
        )

    # =====================================================
    # NEW AES DATA
    # =====================================================

    if encrypted_text.startswith(
        AES_PREFIX
    ):

        try:

            encoded = encrypted_text[
                len(AES_PREFIX):
            ]

            payload = (
                base64.urlsafe_b64decode(
                    encoded.encode("utf-8")
                )
            )

            if len(payload) <= AES_NONCE_SIZE:
                raise ValueError(
                    "Invalid AES encrypted payload"
                )

            nonce = payload[
                :AES_NONCE_SIZE
            ]

            ciphertext = payload[
                AES_NONCE_SIZE:
            ]

            decrypted = aes_cipher.decrypt(
                nonce,
                ciphertext,
                None,
            )

            return decrypted.decode(
                "utf-8"
            )

        except Exception as error:

            raise ValueError(
                "Unable to decrypt AES document data"
            ) from error

    # =====================================================
    # OLD FERNET DATA
    # =====================================================

    try:

        return fernet_cipher.decrypt(
            encrypted_text.encode("utf-8")
        ).decode("utf-8")

    except InvalidToken as error:

        raise ValueError(
            "Unable to decrypt document data"
        ) from error