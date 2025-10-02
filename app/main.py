"""Main application file for FastAPI app"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth_router import router as auth_router
from app.config import settings
from app.database import create_db_and_tables
from app.routers import (
    router_dashboard,
    router_process,
    router_runs,
    router_step_runs,
    router_steps,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan"""
    # Startup: Create database and tables
    create_db_and_tables()
    yield


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(router_dashboard, prefix=settings.API_V1_PREFIX)
app.include_router(router_process, prefix=settings.API_V1_PREFIX)
app.include_router(router_runs, prefix=settings.API_V1_PREFIX)
app.include_router(router_step_runs, prefix=settings.API_V1_PREFIX)
app.include_router(router_steps, prefix=settings.API_V1_PREFIX)


# Root endpoint - health check
@app.get("/", tags=["health"], include_in_schema=False)
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
    }


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
