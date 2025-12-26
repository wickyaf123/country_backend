"""Health check related Pydantic schemas - Story Intelligence Focus."""

from datetime import datetime
from pydantic import BaseModel


class ServiceStatus(BaseModel):
    """Schema for individual service status."""
    
    database: str
    openai: str
    perplexity: str
    apify: str


class HealthResponse(BaseModel):
    """Response schema for health check."""
    
    status: str  # 'ok', 'degraded', 'down'
    timestamp: datetime
    services: ServiceStatus
