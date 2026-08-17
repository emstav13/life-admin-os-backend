import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.routes.documents import router as documents_router
from app.routes.upload import router as upload_router
from app.routes.tasks import router as tasks_router
from app.routes.reminders import router as reminders_router
from app.routes.settings import router as settings_router
from app.routes.subscription import router as subscription_router
from app.services.scheduler import check_reminders


# =========================================================
# LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    reminder_task = asyncio.create_task(
        check_reminders()
    )

    print(
        "Reminder scheduler background task started"
    )

    try:
        yield
    finally:
        reminder_task.cancel()

        try:
            await reminder_task
        except asyncio.CancelledError:
            pass

        print(
            "Reminder scheduler background task stopped"
        )


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Life AiOS API",
    version="1.0.0",
    lifespan=lifespan,
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

        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        response.headers[
            "X-Frame-Options"
        ] = "DENY"

        response.headers[
            "Referrer-Policy"
        ] = (
            "strict-origin-when-cross-origin"
        )

        response.headers[
            "Permissions-Policy"
        ] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=()"
        )

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
        "https://life-aios-flax.vercel.app",
        "https://life-aios-khaf087w6-perso-b1ad.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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