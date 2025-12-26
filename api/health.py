"""Simplified health check and monitoring endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import structlog

from database import get_db
from schemas.health import HealthResponse, ServiceStatus
from config import settings
from services.cache_service import cache_service
from services.rate_limiter import rate_limiter, rate_limit, RATE_LIMIT_CONFIGS

logger = structlog.get_logger()
router = APIRouter()


async def check_database(db: AsyncSession) -> str:
    """Check database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "down"


async def check_openai() -> str:
    """Check OpenAI API configuration."""
    if not settings.openai_api_key:
        return "down"
    return "ok"


async def check_perplexity() -> str:
    """Check Perplexity API configuration."""
    if not settings.perplexity_api_key:
        return "down"
    return "ok"


async def check_apify() -> str:
    """Check Apify API configuration."""
    if not settings.apify_api_key:
        return "down"
    return "ok"


@router.get("/health", response_model=HealthResponse)
@rate_limit(**RATE_LIMIT_CONFIGS["public"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Basic health check endpoint."""
    
    # Check all services
    services = ServiceStatus(
        database=await check_database(db),
        openai=await check_openai(),
        perplexity=await check_perplexity(),
        apify=await check_apify()
    )
    
    # Determine overall status
    service_statuses = [
        services.database,
        services.openai,
        services.perplexity,
        services.apify
    ]
    
    if all(status == "ok" for status in service_statuses):
        overall_status = "ok"
    elif any(status == "down" for status in service_statuses):
        overall_status = "degraded"
    else:
        overall_status = "down"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        services=services
    )


@router.get("/cache/stats")
@rate_limit(**RATE_LIMIT_CONFIGS["api_read"])
async def get_cache_stats():
    """Get cache performance statistics."""
    try:
        # Check if cache_service has get_stats, if not return dummy
        if hasattr(cache_service, 'get_stats'):
            stats = await cache_service.get_stats()
            return stats
        return {"status": "available", "info": "Redis cache active"}
    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Cache stats retrieval failed: {str(e)}")


@router.get("/status")
@rate_limit(**RATE_LIMIT_CONFIGS["public"])
async def get_system_status(db: AsyncSession = Depends(get_db)):
    """Get overall system status summary."""
    try:
        db_status = await check_database(db)
        openai_status = await check_openai()
        
        return {
            "overall_status": "ok" if db_status == "ok" else "critical",
            "components": {
                "database": db_status,
                "openai": openai_status,
                "perplexity": await check_perplexity(),
                "apify": await check_apify()
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "focus": "Story Intelligence Hub"
        }
    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        return {
            "overall_status": "critical",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
