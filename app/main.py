from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.routes.documents import router as documents_router
from app.routes.upload import router as upload_router
from app.routes.tasks import router as tasks_router
from app.routes.reminders import router as reminders_router
from app.routes.settings import router as settings_router
from app.routes.subscription import router as subscription_router


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Life AiOS API",
    version="1.0.0",
)


# =========================================================
# SECURITY HEADERS
# =========================================================

class SecurityHeadersMiddleware(
    BaseHTTPMiddleware
):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        response = await call_next(
            request
        )

        # Prevent MIME-type sniffing
        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        # Prevent clickjacking
        response.headers[
            "X-Frame-Options"
        ] = "DENY"

        # Control referrer information
        response.headers[
            "Referrer-Policy"
        ] = (
            "strict-origin-when-cross-origin"
        )

        # Disable unnecessary browser capabilities
        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=()"
        )

        # HSTS only when actually using HTTPS
        if request.url.scheme == "https":

            response.headers[
                "Strict-Transport-Security"
            ] = (
                "max-age=31536000; "
                "includeSubDomains"
            )

        return response


app.add_middleware(
    SecurityHeadersMiddleware
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:3000",
    ],

    allow_credentials=True,

    allow_methods=[
        "*",
    ],

    allow_headers=[
        "*",
    ],
)


# =========================================================
# ROUTERS
# =========================================================

app.include_router(
    settings_router
)

app.include_router(
    subscription_router
)

app.include_router(
    upload_router
)

app.include_router(
    documents_router
)

app.include_router(
    tasks_router
)

app.include_router(
    reminders_router
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():

    return {
        "status": "ok",
        "service": "Life AiOS API",
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
async def health():

    return {
        "status": "healthy",
    }