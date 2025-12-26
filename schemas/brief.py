"""Brief-related Pydantic schemas."""

from datetime import date, datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel

from .story import StoryResponse


class CompetitorGap(BaseModel):
    """Schema for competitor gap data."""
    
    story_id: UUID
    story_title: str
    missed_by: list[str]
    opportunity_window_hours: int


class GeoTrend(BaseModel):
    """Schema for geographic trend data."""
    
    region: str
    trending_entities: list[str]
    spike_score: float


class BriefContent(BaseModel):
    """Schema for brief content data."""
    
    top_stories: list[StoryResponse]
    predictions: list[str]
    competitor_gaps: list[CompetitorGap]
    geo_trends: list[GeoTrend]
    summary: str


class BriefResponse(BaseModel):
    """Response schema for brief data."""
    
    id: UUID
    date: date
    type: str  # 'morning' or 'evening'
    content: BriefContent
    generated_at: datetime
    story_count: int
    pdf_url: Optional[str] = None
    
    class Config:
        from_attributes = True
