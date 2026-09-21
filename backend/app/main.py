"""GoCars FastAPI Application Entry Point.

Configures:
- Application lifecycle management (lifespan)
- CORS (Cross-Origin Resource Sharing) middleware
- API route mounting with /api/v1 prefix
- OpenAPI / Swagger documentation
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.core.config import settings
from app.routes.api_v1 import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")
    # Automatically verify and seed platform roles if missing
    try:
        from app.core.database import SessionLocal
        from app.repositories.user_repository import UserRepository
        with SessionLocal() as db:
            user_repo = UserRepository(db)
            user_repo.ensure_default_roles()
            db.commit()
        logger.info("Default roles (ADMIN, CUSTOMER, OWNER, DRIVER) verified.")
    except Exception as e:
        logger.warning(f"Role initialization deferred (database not ready or error): {e}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "GoCars is a production-oriented car mobility and rental platform "
        "supporting self-drive rentals, car-with-driver services, fleet management, "
        "and automated booking workflows."
    ),
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect root path to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")
