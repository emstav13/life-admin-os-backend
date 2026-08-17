import os

from dotenv import load_dotenv

from fastapi import (
    Depends,
    HTTPException,
    status,
)

from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from supabase import create_client


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY"
)


if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL is not configured"
    )


if not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_KEY is not configured"
    )


# =========================================================
# SUPABASE AUTH CLIENT
# =========================================================
#
# This client is used only to verify the Supabase
# access token sent by the frontend.
#
# IMPORTANT:
# The actual user's identity always comes from
# the verified access token.
# =========================================================

auth_supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# =========================================================
# HTTP BEARER SECURITY
# =========================================================

security = HTTPBearer(
    auto_error=False
)


# =========================================================
# GET CURRENT AUTHENTICATED USER
# =========================================================

async def get_current_user(
    credentials:
        HTTPAuthorizationCredentials | None =
        Depends(security),
):
    """
    Verify the Supabase access token and return
    the authenticated Supabase user.

    The frontend cannot provide or override user_id.
    """

    # =====================================================
    # AUTHORIZATION HEADER
    # =====================================================

    if credentials is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )


    # =====================================================
    # ACCESS TOKEN
    # =====================================================

    token = (
        credentials.credentials
        or ""
    ).strip()


    if not token:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )


    # =====================================================
    # BASIC JWT FORMAT CHECK
    # =====================================================

    if token.count(".") != 2:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token format",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )


    # =====================================================
    # VERIFY TOKEN WITH SUPABASE
    # =====================================================

    try:

        response = (
            auth_supabase
            .auth
            .get_user(token)
        )


        user = getattr(
            response,
            "user",
            None,
        )


        if user is None:

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session",
                headers={
                    "WWW-Authenticate": "Bearer"
                },
            )


        # =================================================
        # SUCCESS
        # =================================================

        return user


    except HTTPException:
        raise


    except Exception as error:

        # -------------------------------------------------
        # SAFE SERVER-SIDE DIAGNOSTIC
        #
        # Never log:
        # - token
        # - Authorization header
        # - email
        # - user data
        #
        # We log only the exception TYPE.
        # -------------------------------------------------

        print(
            "Supabase authentication error:",
            type(error).__name__,
        )


        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )