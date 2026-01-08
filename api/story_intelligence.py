"""Story Intelligence API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
import structlog
import uuid

from database import get_db
from models.story_intelligence import (
    TrendKeyword, CountryMusicConnection, StoryAngle, RSSStoryLead, PipelineRun
)
from schemas.story_intelligence import (
    StoryIntelligenceDashboard,
    TrendKeywordResponse,
    StoryAngleResponse,
    ConnectionGraphResponse,
    ConnectionGraphNode,
    ConnectionGraphEdge,
    RSSLeadResponse,
    PipelineTriggerResponse,
    PipelineStatusResponse,
    ComponentTestResponse,
    SortByOption
)
from services.story_intelligence_service import story_intelligence_service
from services.rss_realtime_service import rss_realtime_service

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/story-intelligence", tags=["Story Intelligence"])


@router.post("/manual-trigger", response_model=PipelineTriggerResponse)
async def trigger_story_intelligence_pipeline(
    background_tasks: BackgroundTasks,
    timeframe: str = Query(
        default="24",
        description="Timeframe for trending searches: 4, 24, 48, or 168 hours",
        regex="^(4|24|48|168)$"
    ),
    keyword_limit: Optional[int] = Query(
        default=None,
        description="Optional limit on number of keywords to process (for testing)",
        ge=1
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger the complete Story Intelligence pipeline.
    
    Args:
        timeframe: Timeframe for trending searches (4h, 24h, 48h, 168h/7d)
        keyword_limit: Optional limit on keywords (useful for testing with 1 keyword)
    """
    run_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)
    
    logger.info("Manual pipeline trigger initiated", run_id=run_id, timeframe=timeframe)
    
    try:
        # Create pipeline run record
        run = PipelineRun(
            id=run_id,
            status="started",
            progress="Pipeline initiated",
            current_step="started",
            started_at=start_time
        )
        db.add(run)
        await db.commit()
        
        # Run in background with NEW database session (the current `db` will be closed after this request returns)
        async def run_pipeline():
            try:
                from database import AsyncSessionLocal
                async with AsyncSessionLocal() as new_db:
                    try:
                        # Pass timeframe and keyword_limit to the service
                        await story_intelligence_service.run_hourly_intelligence_cycle(
                            new_db, 
                            run_id=run_id, 
                            timeframe=timeframe,
                            keyword_limit=keyword_limit
                        )
                    except Exception as e:
                        logger.error("Background pipeline failed", run_id=run_id, error=str(e), exc_info=True)
            except Exception as outer_e:
                logger.error("Fatal error in background pipeline", run_id=run_id, error=str(outer_e), exc_info=True)
        
        background_tasks.add_task(run_pipeline)
        
        # Estimate time based on timeframe (more keywords = more processing time)
        timeframe_estimates = {
            "4": "2-3 minutes",
            "24": "3-5 minutes",
            "48": "4-6 minutes",
            "168": "5-8 minutes"
        }
        estimated_time = timeframe_estimates.get(timeframe, "3-5 minutes")
        
        return PipelineTriggerResponse(
            status="started",
            run_id=run_id,
            message=f"Story Intelligence pipeline started for {timeframe}h trending searches",
            started_at=start_time.isoformat(),
            estimated_completion=estimated_time,
            check_status_url=f"/api/v1/story-intelligence/status/{run_id}"
        )
    
    except Exception as e:
        logger.error("Pipeline trigger failed", run_id=run_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline failed to start: {str(e)}"
        )


@router.get("/status/{run_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    run_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Check status of a pipeline run."""
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
        
    return run


@router.get("/dashboard", response_model=StoryIntelligenceDashboard)
async def get_dashboard(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db)
):
    """Get Story Intelligence dashboard data."""
    data = await story_intelligence_service.get_story_intelligence_dashboard(
        db, hours=hours
    )
    return data


@router.get("/trending-keywords")
async def get_trending_keywords(
    limit: int = Query(default=50, ge=1, le=100),
    min_connections: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get trending keywords with connection counts, sorted by connections first."""
    # Query with connection count using LEFT JOIN
    query = (
        select(
            TrendKeyword,
            func.count(CountryMusicConnection.id).label('connection_count')
        )
        .outerjoin(CountryMusicConnection, TrendKeyword.id == CountryMusicConnection.keyword_id)
        .group_by(TrendKeyword.id)
        .order_by(
            desc(func.count(CountryMusicConnection.id)),  # Keywords with connections first
            desc(TrendKeyword.search_volume)
        )
    )
    
    if min_connections > 0:
        query = query.having(func.count(CountryMusicConnection.id) >= min_connections)
    
    query = query.limit(limit)
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            "id": row.TrendKeyword.id,
            "keyword": row.TrendKeyword.keyword,
            "search_volume": row.TrendKeyword.search_volume,
            "trend_rank": row.TrendKeyword.trend_rank,
            "connection_count": row.connection_count,
            "parsing_status": row.TrendKeyword.parsing_status,
            "detected_at": row.TrendKeyword.detected_at.isoformat()
        }
        for row in rows
    ]


@router.get("/keyword/{keyword_id}/connections")
async def get_keyword_connections(
    keyword_id: str,
    sort_by: SortByOption = Query(default="confidence"),
    db: AsyncSession = Depends(get_db)
):
    """Get all connections for a specific keyword."""
    query = select(CountryMusicConnection).where(CountryMusicConnection.keyword_id == keyword_id)
    
    if sort_by == "recency":
        query = query.order_by(desc(CountryMusicConnection.discovered_at))
    else:
        query = query.order_by(
            CountryMusicConnection.degree,
            desc(CountryMusicConnection.confidence_score)
        )
        
    result = await db.execute(query)
    connections = result.scalars().all()
    
    if not connections:
        raise HTTPException(status_code=404, detail="No connections found")
    
    # Group by degree
    grouped = {1: [], 2: [], 3: []}
    for conn in connections:
        grouped[conn.degree].append({
            "id": conn.id,
            "type": conn.connection_type,
            "entity": conn.connection_entity,
            "description": conn.connection_description,
            "confidence": conn.confidence_score,
            "chain": conn.connection_chain,
            "evidence": conn.evidence_sources,
            "discovered_at": conn.discovered_at.isoformat()
        })
    
    return {
        "keyword_id": keyword_id,
        "first_degree": grouped[1],
        "second_degree": grouped[2],
        "third_degree": grouped[3]
    }


@router.post("/analyze-keyword")
async def analyze_keyword_connections(
    keyword: str = Query(..., description="Keyword to analyze"),
    deep_research: bool = Query(default=False, description="Enable deep research mode (slower, more thorough)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze connections for a keyword on-demand.
    """
    from services.connection_analyzer_service import connection_analyzer_service
    
    try:
        logger.info(
            "On-demand keyword analysis",
            keyword=keyword,
            deep_research=deep_research
        )
        
        # Note: deep_research parameter kept for API compatibility but not used
        # Connection analyzer always uses sonar-reasoning-pro (fast and reliable)
        connections, parsing_status = await connection_analyzer_service.find_country_music_connections(
            keyword=keyword
        )
        
        return {
            "keyword": keyword,
            "deep_research_mode": deep_research,
            "model_used": "sonar-reasoning-pro",
            "parsing_status": parsing_status,
            "connections": connections,
            "total_found": len(connections),
            "by_degree": {
                "first_degree": len([c for c in connections if c.get("degree") == 1]),
                "second_degree": len([c for c in connections if c.get("degree") == 2]),
                "third_degree": len([c for c in connections if c.get("degree") == 3])
            }
        }
    except Exception as e:
        logger.error("Failed to analyze keyword", keyword=keyword, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/story-angles")
async def get_story_angles(
    unused_only: bool = Query(default=True),
    sort_by: SortByOption = Query(default="urgency"),
    limit: int = Query(default=50, ge=1, le=100),
    # Filters
    connection_degree: Optional[int] = Query(default=None, ge=1, le=3),
    has_rss: Optional[bool] = Query(default=None),
    has_research: Optional[bool] = Query(default=None),
    connection_type: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db)
):
    """Get story angles with comprehensive filtering and RSS data."""
    query = select(StoryAngle, TrendKeyword).join(TrendKeyword, StoryAngle.keyword_id == TrendKeyword.id)
    
    # Apply filters
    if unused_only:
        query = query.where(StoryAngle.is_used == False)
    
    # Sorting
    if sort_by == "recency":
        query = query.order_by(desc(StoryAngle.created_at))
    elif sort_by == "engagement":
        query = query.order_by(desc(StoryAngle.engagement_potential))
    elif sort_by == "volume":
        query = query.order_by(desc(TrendKeyword.search_volume))
    else:  # urgency
        query = query.order_by(desc(StoryAngle.urgency_score))
    
    query = query.limit(limit)
    result = await db.execute(query)
    rows = result.all()
    
    story_angles = []
    for angle, keyword in rows:
        # Get connection for filtering and metadata
        conn_result = await db.execute(
            select(CountryMusicConnection)
            .where(CountryMusicConnection.keyword_id == keyword.id)
            .order_by(CountryMusicConnection.degree, desc(CountryMusicConnection.confidence_score))
            .limit(1)
        )
        conn = conn_result.scalar_one_or_none()
        
        # Apply connection filters (post-query filtering)
        if connection_degree is not None and (not conn or conn.degree != connection_degree):
            continue
        if connection_type is not None and (not conn or conn.connection_type != connection_type):
            continue
        
        # Get RSS articles for this angle
        rss_result = await db.execute(
            select(RSSStoryLead)
            .where(RSSStoryLead.matched_story_angle_id == angle.id)
            .order_by(desc(RSSStoryLead.published_at))
            .limit(5)  # Top 5 articles per angle
        )
        rss_articles = rss_result.scalars().all()
        
        # Apply RSS filter
        if has_rss is not None:
            if has_rss and len(rss_articles) == 0:
                continue
            if not has_rss and len(rss_articles) > 0:
                continue
        
        # Apply research filter
        if has_research is not None:
            if has_research and not angle.deep_research_results:
                continue
            if not has_research and angle.deep_research_results:
                continue
        
        # Build connection path
        path = f"{keyword.keyword}"
        explanation = "Direct trend"
        degree = 1
        conn_type = None
        
        if conn:
            degree = conn.degree
            conn_type = conn.connection_type
            if conn.degree == 1:
                path = f"{keyword.keyword} → {conn.connection_entity}"
            elif conn.degree == 2:
                path = f"{keyword.keyword} → {conn.connection_entity} → Country Music"
            else:  # degree 3
                path = f"{keyword.keyword} → [Cultural/Lifestyle] → {conn.connection_entity} → Country Music"
            explanation = conn.connection_description
        
        # Build response with RSS data
        angle_data = {
            "id": angle.id,
            "keyword_id": angle.keyword_id,
            "headline": angle.headline,
            "angle_description": angle.angle_description,
            "urgency_score": angle.urgency_score,
            "engagement_potential": angle.engagement_potential,
            "uniqueness_score": angle.uniqueness_score,
            "key_facts": angle.key_facts,
            "suggested_sources": angle.suggested_sources,
            "deep_research_results": angle.deep_research_results,
            "connection_path": path,
            "connection_degree": degree,
            "connection_type": conn_type,
            "connection_explanation": explanation,
            "created_at": angle.created_at.isoformat(),
            "is_used": angle.is_used,
            # RSS articles
            "rss_articles": [
                {
                    "id": rss.id,
                    "title": rss.title,
                    "url": rss.url,
                    "source": rss.source_name,
                    "published_at": rss.published_at.isoformat() if rss.published_at else None,
                    "relevance": rss.country_music_relevance
                }
                for rss in rss_articles
            ],
            "rss_article_count": len(rss_articles)
        }
        
        story_angles.append(angle_data)
    
    return story_angles


@router.post("/angle/{angle_id}/deep-research")
async def trigger_deep_research(
    angle_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Trigger Perplexity sonar-deep-research for a specific angle."""
    try:
        results = await story_intelligence_service.perform_deep_research(db, angle_id)
        return {"status": "success", "data": results}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Deep research API failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rss-leads")
async def get_rss_leads(
    hours: int = Query(default=6, ge=1, le=48),
    min_relevance: float = Query(default=0.6, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get recent RSS story leads with keyword information."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Join with TrendKeyword to get keyword name
    result = await db.execute(
        select(RSSStoryLead, TrendKeyword)
        .outerjoin(TrendKeyword, RSSStoryLead.matched_trend_keyword_id == TrendKeyword.id)
        .where(RSSStoryLead.fetched_at >= cutoff)
        .where(RSSStoryLead.country_music_relevance >= min_relevance)
        .order_by(desc(RSSStoryLead.published_at))
        .limit(limit)
    )
    rows = result.all()
    
    return {
        "total": len(rows),
        "leads": [
            {
                "id": lead.id,
                "title": lead.title,
                "url": lead.url,
                "source": lead.source_name,
                "published_at": lead.published_at.isoformat() if lead.published_at else None,
                "relevance": lead.country_music_relevance,
                "keywords": lead.extracted_keywords,
                "matched_keyword_id": lead.matched_trend_keyword_id,
                "matched_keyword_name": keyword.keyword if keyword else None,
                "matched_story_angle_id": lead.matched_story_angle_id
            }
            for lead, keyword in rows
        ]
    }


@router.post("/angle/{angle_id}/mark-used")
async def mark_angle_used(
    angle_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Mark a story angle as used."""
    result = await db.execute(
        select(StoryAngle).where(StoryAngle.id == angle_id)
    )
    angle = result.scalar_one_or_none()
    
    if not angle:
        raise HTTPException(status_code=404, detail="Angle not found")
    
    angle.is_used = True
    await db.commit()
    
    return {"status": "success", "angle_id": angle_id}


@router.get("/connection-graph/{keyword_id}", response_model=ConnectionGraphResponse)
async def get_connection_graph(
    keyword_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get connection graph data for visualization."""
    # Get keyword
    keyword_result = await db.execute(
        select(TrendKeyword).where(TrendKeyword.id == keyword_id)
    )
    keyword = keyword_result.scalar_one_or_none()
    
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")
    
    # Get connections
    conn_result = await db.execute(
        select(CountryMusicConnection)
        .where(CountryMusicConnection.keyword_id == keyword_id)
    )
    connections = conn_result.scalars().all()
    
    # Build graph structure
    nodes = [
        ConnectionGraphNode(
            id=keyword.id,
            label=keyword.keyword,
            type="keyword",
            size=keyword.search_volume / 1000 if keyword.search_volume else 10
        )
    ]
    
    edges = []
    
    for conn in connections:
        node_id = f"conn_{conn.id}"
        nodes.append(ConnectionGraphNode(
            id=node_id,
            label=conn.connection_entity,
            type=conn.connection_type,
            degree=conn.degree
        ))
        
        edges.append(ConnectionGraphEdge(
            source=keyword.id,
            target=node_id,
            label=f"{conn.degree}° - {conn.connection_type}",
            confidence=conn.confidence_score
        ))
    
    return ConnectionGraphResponse(
        nodes=nodes,
        edges=edges
    )


@router.get("/graph-data")
async def get_network_graph_data(
    db: AsyncSession = Depends(get_db)
):
    """
    Get network graph data for Cytoscape visualization.
    Shows all keywords processed by the most recent pipeline run with their connections.
    """
    # Get all keywords from database (no time or limit filters)
    result = await db.execute(
        select(TrendKeyword)
        .order_by(desc(TrendKeyword.search_volume))
    )
    keywords = result.scalars().all()
    
    if not keywords:
        # No keywords yet, return empty graph
        return {
            "nodes": [],
            "edges": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "total_keywords": 0,
                "total_connections": 0,
                "total_rss_articles": 0,
                "total_story_angles": 0
            }
        }
    
    # Get story angles for metadata (keywords can exist without angles)
    angles_result = await db.execute(
        select(StoryAngle)
        .where(StoryAngle.is_used == False)
        .order_by(desc(StoryAngle.urgency_score))
    )
    story_angles = angles_result.scalars().all()
    
    # Build story angle map for quick lookup (keywords may have 0 angles)
    angles_by_keyword = {}
    for angle in story_angles:
        if angle.keyword_id not in angles_by_keyword:
            angles_by_keyword[angle.keyword_id] = []
        angles_by_keyword[angle.keyword_id].append({
            "id": angle.id,
            "headline": angle.headline,
            "description": angle.angle_description,
            "urgency": angle.urgency_score,
            "engagement": angle.engagement_potential,
            "uniqueness": angle.uniqueness_score
        })
    
    # Get keyword IDs for RSS lookup
    keyword_ids = [keyword.id for keyword in keywords]
    
    # Get RSS articles - show all relevant articles, not just matched ones
    rss_result = await db.execute(
        select(RSSStoryLead)
        .where(RSSStoryLead.country_music_relevance >= 0.6)
        .order_by(desc(RSSStoryLead.country_music_relevance))
        .limit(50)
    )
    rss_leads = rss_result.scalars().all()
    
    # Build RSS count map for keywords
    rss_by_keyword = {}
    for rss in rss_leads:
        if rss.matched_trend_keyword_id:
            kid = f"keyword_{rss.matched_trend_keyword_id}"
            if kid not in rss_by_keyword:
                rss_by_keyword[kid] = []
            rss_by_keyword[kid].append(rss)
    
    nodes = []
    edges = []
    all_connections = []
    
    # Add keyword nodes with story angle metadata
    for keyword in keywords:
        keyword_id = f"keyword_{keyword.id}"
        rss_count = len(rss_by_keyword.get(keyword_id, []))
        keyword_angles = angles_by_keyword.get(keyword.id, [])
        
        # Get connections count for this keyword
        conn_count_result = await db.execute(
            select(func.count(CountryMusicConnection.id))
            .where(CountryMusicConnection.keyword_id == keyword.id)
        )
        connection_count = conn_count_result.scalar() or 0
        
        nodes.append({
            "data": {
                "id": keyword_id,
                "label": keyword.keyword,
                "type": "keyword",
                "search_volume": keyword.search_volume or 0,
                "node_size": min((keyword.search_volume or 100) / 100, 50),
                "trend_rank": keyword.trend_rank,
                "rss_article_count": rss_count,
                "has_rss_glow": rss_count > 0,
                "connection_count": connection_count,
                # NEW: Add story angle metadata
                "story_angles": keyword_angles,
                "angle_count": len(keyword_angles),
                "has_story_angles": len(keyword_angles) > 0
            }
        })
        
        # Get ALL connections for this keyword
        conn_result = await db.execute(
            select(CountryMusicConnection)
            .where(CountryMusicConnection.keyword_id == keyword.id)
            .order_by(desc(CountryMusicConnection.confidence_score))
        )
        connections = conn_result.scalars().all()
        all_connections.extend(connections)
        
        # Add connection nodes and edges
        for conn in connections:
            entity_id = f"entity_{conn.id}"
            
            nodes.append({
                "data": {
                    "id": entity_id,
                    "label": conn.connection_entity,
                    "type": conn.connection_type,
                    "degree": conn.degree,
                    "connection_chain": conn.connection_chain,
                    "confidence": conn.confidence_score,
                    "description": conn.connection_description[:100] + "..." if conn.connection_description and len(conn.connection_description) > 100 else conn.connection_description
                }
            })
            
            edges.append({
                "data": {
                    "id": f"edge_{conn.id}",
                    "source": f"keyword_{keyword.id}",
                    "target": entity_id,
                    "degree": conn.degree,
                    "confidence": conn.confidence_score,
                    "label": conn.connection_chain if conn.connection_chain else f"{conn.degree}° - {conn.connection_type}",
                    "chain": conn.connection_chain
                }
            })
    
    # Mark top 5 by confidence in nodes
    top_5_connections = sorted(
        all_connections,
        key=lambda c: c.confidence_score or 0,
        reverse=True
    )[:5]
    top_5_entity_ids = {f"entity_{conn.id}" for conn in top_5_connections}
    
    for node in nodes:
        if node["data"]["id"] in top_5_entity_ids:
            node["data"]["top_priority"] = True
        else:
            node["data"]["top_priority"] = False
    
    # Add RSS layer nodes
    for rss in rss_leads:
        nodes.append({
            "data": {
                "id": f"rss_{rss.id}",
                "label": rss.title[:50] + "..." if len(rss.title) > 50 else rss.title,
                "type": "rss_article",
                "source": rss.source_name,
                "relevance": rss.country_music_relevance,
                "url": rss.url,
                "published_at": rss.published_at.isoformat() if rss.published_at else None,
                "title": rss.title
            }
        })
        
        if rss.matched_trend_keyword_id:
            edges.append({
                "data": {
                    "id": f"rss_edge_{rss.id}",
                    "source": f"keyword_{rss.matched_trend_keyword_id}",
                    "target": f"rss_{rss.id}",
                    "type": "rss_connection",
                    "label": "RSS Match"
                }
            })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_keywords": len(keywords),
            "total_connections": len(all_connections),
            "total_rss_articles": len(rss_leads),
            "total_story_angles": len(story_angles)
        }
    }
