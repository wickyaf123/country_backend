"""Scheduled jobs for Story Intelligence pipeline."""

import asyncio
from datetime import datetime, timedelta, timezone
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete

from database import AsyncSessionLocal
from services.story_intelligence_service import story_intelligence_service
from services.rss_realtime_service import rss_realtime_service
from models.story_intelligence import TrendKeyword

logger = structlog.get_logger()


async def run_story_intelligence_cycle():
    """
    Hourly job that runs the complete Story Intelligence pipeline:
    1. Fetch trending keywords (configurable limit, default 50)
    2. Analyze connections to country music
    3. Generate story angles
    4. Scrape RSS feeds for matching stories
    """
    logger.info("Starting hourly Story Intelligence cycle")
    
    async with AsyncSessionLocal() as db:
        try:
            # Run main intelligence pipeline with 50 keywords by default
            result = await story_intelligence_service.run_hourly_intelligence_cycle(
                db, 
                keyword_limit=50
            )
            
            logger.info(
                "Story Intelligence cycle completed",
                trends=result["trends_fetched"],
                connections=result["connections_found"],
                angles=result["story_angles_generated"]
            )
            
            # Get trending keywords for RSS matching
            keyword_result = await db.execute(
                select(TrendKeyword.keyword)
                .order_by(desc(TrendKeyword.detected_at))
                .limit(100)
            )
            trending_keywords = [kw for kw, in keyword_result.all()]
            
            # Scrape RSS feeds
            rss_leads = await rss_realtime_service.scrape_rss_for_intelligence(
                db, trending_keywords
            )
            
            logger.info(
                "RSS scrape completed",
                leads_found=len(rss_leads)
            )
            
            return {
                "status": "success",
                "pipeline_result": result,
                "rss_leads": len(rss_leads),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Story Intelligence cycle failed", error=str(e), exc_info=True)
            raise


async def cleanup_old_intelligence_data():
    """
    Weekly cleanup job to remove old intelligence data (keep 30 days).
    """
    logger.info("Cleaning up old Story Intelligence data")
    
    async with AsyncSessionLocal() as db:
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            
            # Delete old keywords and their connections/angles (cascade)
            result = await db.execute(
                delete(TrendKeyword).where(TrendKeyword.detected_at < cutoff)
            )
            
            await db.commit()
            
            logger.info(
                "Story Intelligence cleanup completed",
                rows_deleted=result.rowcount
            )
            
        except Exception as e:
            logger.error("Cleanup failed", error=str(e), exc_info=True)
            raise





