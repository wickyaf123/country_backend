"""Story Intelligence models for trend analysis and connection discovery."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TrendKeyword(Base):
    """Trending keywords from Google Trends."""
    
    __tablename__ = "trend_keywords"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    keyword: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    search_volume: Mapped[int] = mapped_column(Integer, default=0)
    trend_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="google_trends")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    apify_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    related_queries: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parsing_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="success")
    # Values: "success", "repaired", "partial", "failed"
    
    # Relationships
    connections: Mapped[list["CountryMusicConnection"]] = relationship(
        "CountryMusicConnection",
        back_populates="keyword",
        cascade="all, delete-orphan"
    )
    story_angles: Mapped[list["StoryAngle"]] = relationship(
        "StoryAngle",
        back_populates="keyword",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<TrendKeyword(id={self.id}, keyword='{self.keyword}', rank={self.trend_rank})>"


class CountryMusicConnection(Base):
    """Multi-degree connections from keywords to country music."""
    
    __tablename__ = "country_music_connections"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    keyword_id: Mapped[str] = mapped_column(String(36), ForeignKey("trend_keywords.id"), nullable=False)
    
    # Connection details
    degree: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, or 3
    connection_type: Mapped[str] = mapped_column(String(100), nullable=False)
    connection_entity: Mapped[str] = mapped_column(String(500), nullable=False)
    connection_description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Connection metadata
    connection_chain: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Evidence
    evidence_sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    keyword: Mapped["TrendKeyword"] = relationship("TrendKeyword", back_populates="connections")
    
    def __repr__(self) -> str:
        return f"<CountryMusicConnection(id={self.id}, degree={self.degree}, entity='{self.connection_entity}')>"


class StoryAngle(Base):
    """AI-discovered story angles."""
    
    __tablename__ = "story_angles"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    keyword_id: Mapped[str] = mapped_column(String(36), ForeignKey("trend_keywords.id"), nullable=False)
    
    # Story details
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    angle_description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Metadata
    urgency_score: Mapped[float] = mapped_column(Float, default=0.0)
    uniqueness_score: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_potential: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Supporting data
    key_facts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    suggested_sources: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    competitor_coverage: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    deep_research_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    keyword: Mapped["TrendKeyword"] = relationship("TrendKeyword", back_populates="story_angles")
    rss_articles: Mapped[list["RSSStoryLead"]] = relationship(
        "RSSStoryLead",
        back_populates="matched_story_angle",
        foreign_keys="[RSSStoryLead.matched_story_angle_id]"
    )
    
    def __repr__(self) -> str:
        return f"<StoryAngle(id={self.id}, headline='{self.headline[:50]}...', urgency={self.urgency_score})>"


class RSSStoryLead(Base):
    """Real-time RSS story leads for Story Intelligence."""
    
    __tablename__ = "rss_story_leads"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Analysis
    extracted_keywords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    country_music_relevance: Mapped[float] = mapped_column(Float, default=0.0)
    matched_trend_keyword_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # RSS-to-StoryAngle relationship
    matched_story_angle_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("story_angles.id"), nullable=True)
    matched_country_entity: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    matched_story_angle: Mapped[Optional["StoryAngle"]] = relationship("StoryAngle", back_populates="rss_articles")
    
    def __repr__(self) -> str:
        return f"<RSSStoryLead(id={self.id}, source='{self.source_name}', relevance={self.country_music_relevance})>"


class PipelineRun(Base):
    """Tracks the status and progress of Story Intelligence pipeline runs."""
    
    __tablename__ = "pipeline_runs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # started, fetching_trends, analyzing_connections, generating_angles, completed, failed
    progress: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    def __repr__(self) -> str:
        return f"<PipelineRun(id={self.id}, status='{self.status}', step='{self.current_step}')>"

