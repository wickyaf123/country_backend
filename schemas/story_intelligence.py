"""Pydantic schemas for Story Intelligence API."""

from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

# Sorting options
SortByOption = Literal["recency", "confidence", "urgency", "engagement", "volume"]


class RSSArticleBrief(BaseModel):
    """Brief RSS article info for story angles."""
    id: str
    title: str
    url: str
    source: str
    published_at: Optional[str] = None
    relevance: float


class TrendKeywordResponse(BaseModel):
    """Response model for trending keyword."""
    id: str
    keyword: str
    search_volume: int
    trend_rank: Optional[int] = None
    detected_at: datetime
    connection_count: int = 0
    
    class Config:
        from_attributes = True


class ConnectionResponse(BaseModel):
    """Response model for a connection."""
    id: str
    degree: int
    connection_type: str
    connection_entity: str
    connection_description: str
    confidence_score: float
    connection_chain: Optional[str] = None
    evidence_sources: Optional[Dict[str, Any]] = None
    discovered_at: datetime
    
    class Config:
        from_attributes = True


class StoryAngleResponse(BaseModel):
    """Response model for story angle."""
    id: str
    keyword_id: str
    headline: str
    angle_description: str
    urgency_score: float
    uniqueness_score: float
    engagement_potential: float
    key_facts: Optional[Dict[str, Any]] = None
    suggested_sources: Optional[Dict[str, Any]] = None
    deep_research_results: Optional[Dict[str, Any]] = None
    # Connection metadata
    connection_path: Optional[str] = None
    connection_explanation: Optional[str] = None
    connection_degree: Optional[int] = None
    connection_type: Optional[str] = None
    # RSS articles
    rss_articles: List[RSSArticleBrief] = []
    rss_article_count: int = 0
    created_at: datetime
    is_used: bool
    
    class Config:
        from_attributes = True


class RSSLeadResponse(BaseModel):
    """Response model for RSS story lead."""
    id: str
    title: str
    url: str
    source_name: str
    published_at: Optional[datetime] = None
    extracted_keywords: Optional[Dict[str, Any]] = None
    country_music_relevance: float
    fetched_at: datetime
    
    class Config:
        from_attributes = True


class ConnectionGraphNode(BaseModel):
    """Node in connection graph."""
    id: str
    label: str
    type: str
    size: Optional[float] = None
    degree: Optional[int] = None


class ConnectionGraphEdge(BaseModel):
    """Edge in connection graph."""
    source: str
    target: str
    label: str
    confidence: float


class ConnectionGraphResponse(BaseModel):
    """Response model for connection graph visualization."""
    nodes: List[ConnectionGraphNode]
    edges: List[ConnectionGraphEdge]


class BucketAngle(BaseModel):
    """Story angle within a bucket."""
    id: str
    headline: str
    urgency: float
    engagement: float
    keyword: Optional[str] = None


class ContentBucket(BaseModel):
    """Content bucket with story angles."""
    bucket_name: str
    count: int
    angles: List[BucketAngle]


class StoryIntelligenceDashboard(BaseModel):
    """Dashboard data response."""
    trending_keywords: List[Dict[str, Any]]
    story_angles: List[StoryAngleResponse]
    total_angles: int
    timestamp: str


class PipelineTriggerResponse(BaseModel):
    """Response for manual pipeline trigger."""
    status: str
    run_id: str
    message: str
    started_at: str
    estimated_completion: str
    check_status_url: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    """Response for pipeline status check."""
    id: str
    status: str
    progress: Optional[str] = None
    current_step: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class ComponentTestResponse(BaseModel):
    """Response for component testing."""
    component: str
    status: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


