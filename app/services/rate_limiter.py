from slowapi import Limiter
from slowapi.util import get_remote_address


# =========================================================
# RATE LIMITER
# =========================================================
#
# Rate limiting is currently performed by client IP.
#
# This is intentionally separate from authentication.
# Authentication remains responsible for verifying the
# Supabase access token and authenticated user identity.
#
# For a multi-instance production deployment, we can later
# move the limiter storage to Redis.
# =========================================================

limiter = Limiter(
    key_func=get_remote_address,
)