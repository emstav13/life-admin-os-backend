import os

from dotenv import load_dotenv

from fastapi import (
    Depends,
    HTTPException,
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
# AUTHENTICATION CLIENT
# =========================================================
#
# Dedicated server-side client used only for
# Supabase access-token verification.
#
# No access token is logged.
# No Authorization header is logged.
# No user_id is accepted from the frontend.
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

    The authenticated identity comes exclusively
    from the verified access token.

    The frontend cannot provide or override user_id.
    """

    # =====================================================
    # CHECK AUTHORIZATION HEADER
    # =====================================================

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
        )


    # =====================================================
    # GET ACCESS TOKEN
    # =====================================================

    token = credentials.credentials


    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing access token",
        )


    # =====================================================
    # BASIC JWT FORMAT CHECK
    # =====================================================

    if token.count(".") != 2:
        raise HTTPException(
            status_code=401,
            detail="Invalid access token format",
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

        user = response.user


        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired session",
            )


        # =================================================
        # VERIFIED USER
        # =================================================

        return user


    except HTTPException:
        raise


    except Exception:
        # Never log:
        # - access token
        # - Authorization header
        # - user data
        # - exception contents

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
        )