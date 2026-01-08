"""Main FastAPI application entry point."""

import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from config import settings
from database import create_tables, get_database
from api import health, story_intelligence


# Configure Python's standard logging to output to console
logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)

# Configure structured logging with console renderer for better visibility
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        # Use ConsoleRenderer for human-readable output (better for development)
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Country Rebel SIS application")
    
    # Create database tables
    await create_tables()
    
    # Initialize cache service
    from services.cache_service import cache_service
    await cache_service.initialize()
    
    # Note: No scheduler - using manual triggers only
    logger.info("Story Intelligence ready - use manual triggers via API")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Country Rebel SIS application")


# Create FastAPI application
app = FastAPI(
    title="Country Rebel Story Intelligence System",
    description="A comprehensive system for monitoring, analyzing, and alerting on country music stories and trends",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Add middleware
# CORS: Always allow the Vercel frontend + local development
allowed_origins = [
    "http://localhost:8080",
    "http://localhost:8081", 
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:5173",
    "https://country-frontend-liart.vercel.app"
]

if settings.debug:
    allowed_origins = ["*"]  # Allow all in debug mode

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Allow all hosts (Railway proxies requests)
)

# Include API routers - Story Intelligence Only
app.include_router(health.router, tags=["health"])
app.include_router(story_intelligence.router, tags=["story-intelligence"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Country Rebel Story Intelligence System API",
        "version": "1.0.0",
        "docs": f"{settings.app_base_url}/docs" if settings.debug else None,
        "focus": "Story Intelligence Only - Manual Triggers"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
