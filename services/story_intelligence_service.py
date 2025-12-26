"""AI Research Agent using Apify Google Search for Story Intelligence."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, delete

from config import settings
from models.story_intelligence import TrendKeyword, CountryMusicConnection, StoryAngle, PipelineRun, RSSStoryLead
from services.apify_client import ApifyClient
from services.openai_service import OpenAIService

logger = structlog.get_logger()


class StoryIntelligenceService:
    """
    Orchestrates the entire Story Intelligence pipeline:
    1. Fetch top 100 Google Trends
    2. Analyze connections to country music (1st, 2nd, 3rd degree)
    3. Generate story angles
    """
    
    def __init__(self):
        self.openai_service = OpenAIService()
    
    async def run_hourly_intelligence_cycle(
        self, 
        db: AsyncSession, 
        run_id: Optional[str] = None,
        keyword_limit: int = 50
    ) -> Dict[str, Any]:
        """
        Main hourly cycle that runs the entire intelligence pipeline.
        
        Args:
            db: Database session
            run_id: Optional pipeline run ID for tracking
            keyword_limit: Number of keywords to process (default: 50)
        """
        logger.info("Starting Story Intelligence hourly cycle", run_id=run_id, keyword_limit=keyword_limit)
        
        try:
            # Step 0: Clear ALL previous data for completely fresh start
            if run_id:
                await self._update_pipeline_run(db, run_id, "clearing_data", "Clearing all previous pipeline data")
            
            cleanup_count = await self._clear_all_data(db)
            logger.info(f"Cleared {cleanup_count} previous keywords - starting with fresh data")
            
            # Step 1: Fetch only the trending keywords we need
            if run_id:
                await self._update_pipeline_run(db, run_id, "fetching_trends", f"Fetching top {keyword_limit} Google Trends")
            
            trends = await self.fetch_trending_keywords(limit=keyword_limit)
            logger.info(f"Fetched {len(trends)} trending keywords")
            
            # Step 2: Save all fetched keywords to database
            keyword_records = await self.save_trend_keywords(db, trends)
            logger.info(f"Processing {len(keyword_records)} keywords")
            
            # Step 3: Analyze connections to country music (parallel processing)
            if run_id:
                await self._update_pipeline_run(db, run_id, "analyzing_connections", f"Analyzing connections for {len(keyword_records)} keywords")
            
            connection_results = await self.analyze_all_connections(
                db, keyword_records
            )
            logger.info(f"Found {len(connection_results)} country music connections")
            
            # Step 4: Generate story angles for keywords with strong connections
            if run_id:
                await self._update_pipeline_run(db, run_id, "generating_angles", f"Generating story angles for {len(connection_results)} connections")
            
            story_angles = await self.generate_story_angles(
                db, connection_results
            )
            logger.info(f"Generated {len(story_angles)} story angles")
            
            # Step 5: Fetch and match RSS articles to enrich story angles
            if run_id:
                await self._update_pipeline_run(db, run_id, "enriching_with_rss", f"Fetching RSS articles for {len(story_angles)} angles")
            
            enriched_count = await self.enrich_angles_with_rss(db, story_angles, keyword_records)
            logger.info(f"Enriched {enriched_count} story angles with RSS articles")
            
            # Finalize
            if run_id:
                results = {
                    "trends_fetched": len(trends),
                    "connections_found": len(connection_results),
                    "story_angles_generated": len(story_angles),
                    "rss_articles_matched": enriched_count
                }
                await self._update_pipeline_run(db, run_id, "completed", "Pipeline completed successfully", results=results)
            
            return {
                "status": "success",
                "trends_fetched": len(trends),
                "connections_found": len(connection_results),
                "story_angles_generated": len(story_angles),
                "rss_articles_matched": enriched_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error("Story Intelligence cycle failed", error=str(e), exc_info=True)
            if run_id:
                await self._update_pipeline_run(db, run_id, "failed", f"Error: {str(e)}")
            raise
    
    async def _update_pipeline_run(self, db: AsyncSession, run_id: str, status: str, progress: str, results: Optional[Dict] = None):
        """Helper to update pipeline run status."""
        result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            run.status = status
            run.progress = progress
            run.current_step = status
            if status in ["completed", "failed"]:
                run.completed_at = datetime.now(timezone.utc)
            if results:
                run.results = results
            await db.commit()
    
    async def _clear_all_data(self, db: AsyncSession) -> int:
        """
        Clear ALL previous trend keywords and their related data.
        Provides a completely fresh start for each pipeline run.
        
        Returns:
            Number of keywords deleted
        """
        # Delete child records first to avoid foreign key constraint violations
        # 1. Delete ALL RSS leads
        await db.execute(delete(RSSStoryLead))
        
        # 2. Delete ALL story angles
        await db.execute(delete(StoryAngle))
        
        # 3. Delete ALL country music connections
        await db.execute(delete(CountryMusicConnection))
        
        # 4. Now safe to delete ALL keywords
        result = await db.execute(delete(TrendKeyword))
        deleted_count = result.rowcount
        
        # Keep only last 50 pipeline runs for basic history tracking
        old_runs = await db.execute(
            select(PipelineRun.id)
            .order_by(desc(PipelineRun.started_at))
            .offset(50)
        )
        old_run_ids = [r[0] for r in old_runs.all()]
        if old_run_ids:
            await db.execute(
                delete(PipelineRun).where(PipelineRun.id.in_(old_run_ids))
            )
        
        await db.commit()
        
        logger.info(
            "All previous data cleared for fresh pipeline run",
            keywords_deleted=deleted_count
        )
        
        return deleted_count

    async def perform_deep_research(self, db: AsyncSession, angle_id: str) -> Dict[str, Any]:
        """
        Perform on-demand deep research for a specific story angle using Perplexity sonar-deep-research.
        """
        from services.perplexity_service import perplexity_service
        
        # Get angle and related keyword/connections
        result = await db.execute(
            select(StoryAngle).where(StoryAngle.id == angle_id)
        )
        angle = result.scalar_one_or_none()
        if not angle:
            raise ValueError("Story angle not found")
            
        keyword_result = await db.execute(
            select(TrendKeyword).where(TrendKeyword.id == angle.keyword_id)
        )
        keyword = keyword_result.scalar_one_or_none()
        
        logger.info("Starting deep research for angle", angle_id=angle_id, headline=angle.headline)
        
        system_prompt = """You are a senior investigative journalist specializing in the country music industry. 

🚨 CRITICAL: Focus EXCLUSIVELY on the LAST 90 DAYS. Your timeline should ONLY include events, mentions, and developments from this period.

Your goal is to search exhaustively for ALL mentions, interactions, social media activity, news coverage, podcast appearances, events, and connections from the last 90 days related to this story angle. Cast a wide net.

Focus on factual accuracy, specific quotes, and high-impact details with precise timing.

⚠️ IMPORTANT: Keep your response CONCISE. Limit timeline to 10 most significant events. Keep quotes brief.

🎯 OUTPUT FORMAT: You MUST return ONLY valid JSON. No markdown, no explanations, no code blocks - just pure JSON."""

        query = f"""Perform DEEP RESEARCH on the following story angle: "{angle.headline}".
        
Context:
- Primary Trend: {keyword.keyword if keyword else "N/A"}
- Angle Description: {angle.angle_description}

🎯 SEARCH REQUIREMENTS - Be Comprehensive but Concise:
Search exhaustively for ALL activity in the last 90 days:
- News articles and press releases
- Social media posts (Twitter, Instagram, TikTok, Facebook)
- Podcast episodes and radio interviews
- Live events, concerts, award shows
- Trending topics and viral moments
- Community discussions and fan reactions
- Collaborations and partnerships

⚠️ IMPORTANT: Limit to TOP 10 most significant items per section.

Please provide:
1. TIMELINE: Top 10 most significant events, mentions, posts, or interactions from the last 90 days
2. DETAILED BRIEF: A 2-3 paragraph deep dive explaining the significance and WHY this matters RIGHT NOW
3. KEY QUOTES: Top 3-5 direct quotes from artists, interviews, social media posts, or news sources (all from last 90 days)
4. ACTIONABLE HOOKS: 3 specific ways an editor could frame this story right now (emphasize the recency and timeliness)
5. SOURCE CITATIONS: ALL URLs used for this research (articles, social media posts, podcasts, everything)

Return ONLY this exact JSON structure with no additional text:
{{
  "timeline": [
    {{"date": "December 15, 2024", "event": "Specific event or mention with details"}},
    {{"date": "December 8, 2024", "event": "Another event..."}}
  ],
  "briefing": "Comprehensive explanation of why this is significant NOW...",
  "quotes": [
    {{"speaker": "Artist Name", "text": "Exact quote from recent interview/post"}},
    {{"speaker": "Source", "text": "Another quote..."}}
  ],
  "hooks": [
    "Hook 1 emphasizing recent development",
    "Hook 2 highlighting timeliness",
    "Hook 3 focusing on current relevance"
  ],
  "citations": ["https://url1.com", "https://url2.com", "..."]
}}

DO NOT include markdown formatting, code blocks, or any text outside the JSON structure."""

        try:
            # Use sonar-reasoning-pro instead of deep-research
            # Deep-research returns long-form prose/markdown, not structured JSON
            logger.info(
                "Starting deep research with sonar-reasoning-pro",
                angle_id=angle_id,
                headline=angle.headline
            )
            
            research_result = await perplexity_service.search_and_analyze(
                query=query,
                system_prompt=system_prompt,
                model="sonar-reasoning-pro",  # Better for structured JSON output
                temperature=0.3
            )
            
            # Parse JSON from content
            content = research_result.get("content", "")
            
            logger.info(
                "Perplexity response received",
                angle_id=angle_id,
                content_length=len(content),
                starts_with=content[:50] if content else "EMPTY",
                model_used=research_result.get("model_used")
            )
            
            # Check if content is empty
            if not content or content.strip() == "":
                logger.error("Empty response from Perplexity", angle_id=angle_id)
                raise ValueError("Perplexity returned empty response. The model may not be available or API quota exceeded.")
            
            # Extract JSON from various wrapper formats
            # Handle <think> tags from reasoning models
            if "<think>" in content:
                # Extract content after </think> tag
                if "</think>" in content:
                    content = content.split("</think>", 1)[1].strip()
                else:
                    # If no closing tag, remove opening tag
                    content = content.replace("<think>", "").strip()
            
            # Extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                # Try to extract JSON from any code block
                parts = content.split("```")
                for i, part in enumerate(parts):
                    if i % 2 == 1:  # Odd indices are inside code blocks
                        part = part.strip()
                        # Remove language identifier if present
                        if '\n' in part:
                            lines = part.split('\n', 1)
                            if lines[0].strip() in ['json', 'JSON', '']:
                                part = lines[1] if len(lines) > 1 else part
                        if part.startswith('{') or part.startswith('['):
                            content = part
                            break
            
            # If still looks like markdown (starts with #), try to find JSON in the content
            if content.strip().startswith('#') or not content.strip().startswith('{'):
                # Look for JSON object in the text
                json_start = content.find('{')
                if json_start > -1:
                    # Find the matching closing brace
                    brace_count = 0
                    json_end = -1
                    for i in range(json_start, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                    
                    if json_end > json_start:
                        content = content[json_start:json_end]
                    else:
                        # No valid JSON found, create a structured response from markdown
                        logger.warning(
                            "Perplexity returned markdown instead of JSON, converting",
                            angle_id=angle_id
                        )
                        content = json.dumps({
                            "timeline": [],
                            "briefing": content[:1000],  # Use first 1000 chars as briefing
                            "quotes": [],
                            "hooks": [
                                "Breaking story angle based on recent research",
                                "Timely connection to country music trends",
                                "Exclusive insights from recent developments"
                            ],
                            "citations": research_result.get("citations", []),
                            "_note": "Response was in markdown format, partial conversion applied"
                        })
            
            logger.info(
                "After content extraction",
                angle_id=angle_id,
                content_length_after=len(content),
                starts_with_after=content[:100] if content else "EMPTY"
            )
            
            # Try to parse JSON
            import json
            import re
            
            try:
                data = json.loads(content)
            except json.JSONDecodeError as je:
                logger.warning(
                    "Initial JSON parse failed, attempting fix",
                    angle_id=angle_id,
                    error=str(je),
                    error_pos=f"line {je.lineno} col {je.colno}"
                )
                
                # Try to fix common JSON issues
                # 1. Remove trailing incomplete content
                try:
                    content_fixed = content.rstrip()
                    
                    # If error mentions delimiter or unterminated string, truncate to last valid point
                    if "delimiter" in str(je) or "Unterminated" in str(je) or "Expecting" in str(je):
                        # Find position of error
                        error_pos = je.pos if hasattr(je, 'pos') else len(content_fixed)
                        
                        # Backtrack to find a safe truncation point
                        # Look for the last complete array/object before the error
                        truncate_pos = error_pos
                        for i in range(error_pos - 1, max(0, error_pos - 500), -1):
                            if content_fixed[i] in [']', '}']:
                                truncate_pos = i + 1
                                break
                            elif content_fixed[i] == ',':
                                truncate_pos = i
                                break
                        
                        content_fixed = content_fixed[:truncate_pos].rstrip().rstrip(',').rstrip()
                    
                    # If JSON is incomplete, try to close it properly
                    if not content_fixed.endswith('}'):
                        # Count braces and brackets to close properly
                        open_braces = content_fixed.count('{') - content_fixed.count('}')
                        open_brackets = content_fixed.count('[') - content_fixed.count(']')
                        
                        # Add necessary closing characters
                        if open_brackets > 0:
                            content_fixed += ']' * open_brackets
                        if open_braces > 0:
                            content_fixed += '}' * open_braces
                    
                    data = json.loads(content_fixed)
                    logger.warning(
                        "Successfully fixed truncated JSON response from Perplexity",
                        angle_id=angle_id,
                        original_length=len(content),
                        fixed_length=len(content_fixed),
                        original_error=str(je)
                    )
                except Exception as fix_error:
                    logger.error(
                        "Failed to parse and fix JSON from Perplexity", 
                        angle_id=angle_id,
                        parse_error=str(je),
                        fix_error=str(fix_error),
                        content_preview=content[:500] if content else "EMPTY"
                    )
                    raise ValueError(f"Could not parse Perplexity response as JSON. The API may have returned an error or the sonar-deep-research model may not be available. Error: {str(je)}")
            
            # Add Perplexity citations to the data
            if not data.get("citations"):
                data["citations"] = research_result.get("citations", [])
            
            # Add metadata about which model was used
            data["_metadata"] = {
                "model_used": research_result.get("model_used", "unknown"),
                "research_date": datetime.now(timezone.utc).isoformat()
            }
            
            # Update angle in DB
            angle.deep_research_results = data
            await db.commit()
            
            logger.info(
                "Deep research completed successfully",
                angle_id=angle_id,
                model_used=research_result.get("model_used"),
                timeline_events=len(data.get("timeline", [])),
                citations_count=len(data.get("citations", []))
            )
            
            return data
            
        except Exception as e:
            logger.error("Deep research failed", angle_id=angle_id, error=str(e))
            raise

    async def fetch_trending_keywords(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch top N trending keywords from Google Trends using Apify.
        
        Args:
            limit: Number of trending keywords to fetch (default: 100)
        """
        async with ApifyClient() as client:
            # Trending Now - gets real-time trends
            result = await client.run_google_trends_advanced(
                scrape_type="trending_now",
                geo="US",
                trending_hours=24,
                trending_language="en"
            )
            
            # Transform and sort by search volume
            trends_data = client.transform_advanced_trends_data(result)
            
            # Sort by search volume and take top N (based on limit)
            sorted_trends = sorted(
                trends_data,
                key=lambda x: x.search_volume,
                reverse=True
            )[:limit]
            
            return [
                {
                    "keyword": t.keyword,
                    "search_volume": t.search_volume,
                    "related_queries": t.related_queries,
                    "apify_run_id": t.apify_run_id
                }
                for t in sorted_trends
            ]
    
    async def save_trend_keywords(
        self,
        db: AsyncSession,
        trends: List[Dict[str, Any]]
    ) -> List[TrendKeyword]:
        """Save trend keywords to database."""
        keyword_records = []
        
        for i, trend in enumerate(trends, 1):
            keyword = TrendKeyword(
                keyword=trend["keyword"],
                search_volume=trend["search_volume"],
                trend_rank=i,
                source="google_trends",
                apify_run_id=trend["apify_run_id"],
                related_queries={"queries": trend.get("related_queries", [])}
            )
            db.add(keyword)
            keyword_records.append(keyword)
        
        await db.commit()
        
        # Refresh to get IDs
        for keyword in keyword_records:
            await db.refresh(keyword)
        
        return keyword_records
    
    async def analyze_all_connections(
        self,
        db: AsyncSession,
        keywords: List[TrendKeyword]
    ) -> List[CountryMusicConnection]:
        """
        Analyze connections to country music for all keywords.
        Process in batches to avoid rate limits.
        """
        from services.connection_analyzer_service import connection_analyzer_service
        
        connections = []
        batch_size = 50  # Increased batch size for high parallelism (requested 50 keywords)
        
        for i in range(0, len(keywords), batch_size):
            batch = keywords[i:i+batch_size]
            
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(keywords) + batch_size - 1)//batch_size}")
            
            # Process batch in parallel
            tasks = [
                connection_analyzer_service.find_country_music_connections(
                    keyword.keyword
                )
                for keyword in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Save connections that were found
            for keyword, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(
                        "Connection analysis failed",
                        keyword=keyword.keyword,
                        error=str(result)
                    )
                    # Set parsing status to failed
                    keyword.parsing_status = "failed"
                    continue
                
                # Result is now a tuple of (connections, parsing_status)
                conn_list, parsing_status = result
                
                # Update keyword with parsing status
                keyword.parsing_status = parsing_status
                
                if conn_list:  # Has connections
                    for conn in conn_list:
                        connection = CountryMusicConnection(
                            keyword_id=keyword.id,
                            degree=conn["degree"],
                            connection_type=conn["type"],
                            connection_entity=conn["entity"],
                            connection_description=conn["description"],
                            confidence_score=conn["confidence"],
                            evidence_sources={"sources": conn["evidence"]},
                            connection_chain=conn.get("connection_chain")
                        )
                        db.add(connection)
                        connections.append(connection)
            
            await db.commit()
            
            # Brief pause between batches
            if i + batch_size < len(keywords):
                await asyncio.sleep(2)
        
        return connections
    
    async def generate_story_angles(
        self,
        db: AsyncSession,
        connections: List[CountryMusicConnection]
    ) -> List[StoryAngle]:
        """
        Generate story angles directly from network graph connections.
        Simple representation of graph data - no AI generation.
        Users can then select specific angles for deep research.
        """
        story_angles = []
        
        # Group connections by keyword
        keyword_connections = {}
        for conn in connections:
            if conn.keyword_id not in keyword_connections:
                keyword_connections[conn.keyword_id] = []
            keyword_connections[conn.keyword_id].append(conn)
        
        # Create story angles from connections
        for keyword_id, conns in keyword_connections.items():
            # Get keyword
            result = await db.execute(
                select(TrendKeyword).where(TrendKeyword.id == keyword_id)
            )
            keyword = result.scalar_one_or_none()
            
            if not keyword:
                continue
            
            # Sort by confidence score (highest first)
            conns.sort(key=lambda x: x.confidence_score, reverse=True)
            
            # Create one story angle per connection
            for conn in conns:  # All connections per keyword
                # Build headline from connection data
                headline = self._build_headline_from_connection(keyword.keyword, conn)
                
                # Calculate scores from connection data
                urgency_score = min(conn.confidence_score * 1.2, 1.0)  # Boost high confidence
                uniqueness_score = max(1.0 - (conn.degree * 0.15), 0.4)  # Closer = more unique
                engagement_potential = conn.confidence_score
                
                # Format key facts from connection chain
                key_facts = {
                    "connection_chain": conn.connection_chain,
                    "degree": conn.degree,
                    "connection_type": conn.connection_type,
                    "entity": conn.connection_entity
                }
                
                story_angle = StoryAngle(
                    keyword_id=keyword.id,
                    headline=headline,
                    angle_description=conn.connection_description,
                    urgency_score=urgency_score,
                    uniqueness_score=uniqueness_score,
                    engagement_potential=engagement_potential,
                    key_facts=key_facts,
                    suggested_sources=conn.evidence_sources or {}
                )
                db.add(story_angle)
                story_angles.append(story_angle)
        
        await db.commit()
        logger.info(f"Generated {len(story_angles)} story angles from network graph")
        return story_angles
    
    async def enrich_angles_with_rss(
        self,
        db: AsyncSession,
        story_angles: List[StoryAngle],
        keywords: List[TrendKeyword]
    ) -> int:
        """
        Fetch RSS articles and match them to story angles.
        Matching criteria: Article must mention BOTH the trending keyword AND the country music entity.
        """
        from services.rss_realtime_service import rss_realtime_service
        
        if not story_angles:
            logger.info("No story angles to enrich with RSS")
            return 0
        
        # Extract trending keywords for RSS scraping
        trending_keywords = [kw.keyword for kw in keywords]
        
        logger.info(f"Fetching RSS articles for {len(trending_keywords)} keywords")
        
        # Fetch RSS articles
        rss_articles = await rss_realtime_service.scrape_rss_for_intelligence(db, trending_keywords)
        
        if not rss_articles:
            logger.info("No RSS articles found")
            return 0
        
        logger.info(f"Found {len(rss_articles)} RSS articles, matching to story angles")
        
        # Build entity map from story angles: {keyword_lower: [(angle_id, entity_lower), ...]}
        angle_entity_map = {}
        for angle in story_angles:
            keyword_id = angle.keyword_id
            keyword = next((k for k in keywords if k.id == keyword_id), None)
            if keyword and angle.key_facts:
                entity = angle.key_facts.get("entity")
                if entity:
                    keyword_text = keyword.keyword.lower()
                    if keyword_text not in angle_entity_map:
                        angle_entity_map[keyword_text] = []
                    angle_entity_map[keyword_text].append((angle.id, entity.lower()))
        
        # Match RSS articles to angles (keyword OR entity in title - one is good, both is great)
        enriched_count = 0
        for article in rss_articles:
            title_lower = article.title.lower()
            
            # Find matching angles - either keyword OR entity in title
            for keyword_lower, angle_entities in angle_entity_map.items():
                keyword_match = keyword_lower in title_lower
                
                for angle_id, entity_lower in angle_entities:
                    entity_match = entity_lower in title_lower
                    
                    # Match if EITHER keyword OR entity is present (both is even better!)
                    if keyword_match or entity_match:
                        # Match found!
                        article.matched_story_angle_id = angle_id
                        article.matched_country_entity = entity_lower
                        
                        # Track match quality (both = stronger match)
                        match_quality = "both" if (keyword_match and entity_match) else "partial"
                        enriched_count += 1
                        
                        logger.debug(
                            "RSS match found",
                            article_title=article.title[:50],
                            keyword=keyword_lower,
                            entity=entity_lower,
                            match_quality=match_quality
                        )
                        break  # Only match to first qualifying angle
                if article.matched_story_angle_id:
                    break  # Article matched, move to next article
        
        await db.commit()
        logger.info(f"Matched {enriched_count} RSS articles to story angles")
        return enriched_count
    
    def _build_headline_from_connection(self, keyword: str, conn: CountryMusicConnection) -> str:
        """Build a headline directly from network graph connection data."""
        entity = conn.connection_entity
        conn_type = conn.connection_type.replace('_', ' ').title()
        
        if conn.degree == 1:
            # Direct connection - make it punchy
            return f"{keyword} + {entity}: {conn_type}"
            
        elif conn.degree == 2:
            # 2-degree connection
            return f"{keyword} to Country Music via {entity}"
            
        else:
            # 3-degree connection
            return f"The {keyword}-{entity} Country Music Connection"
    
    async def get_story_intelligence_dashboard(
        self,
        db: AsyncSession,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get dashboard data for the Story Intelligence page.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Get recent keywords with connection counts - limited to 50 for performance
        keywords_result = await db.execute(
            select(
                TrendKeyword,
                func.count(CountryMusicConnection.id).label('connection_count')
            )
            .outerjoin(CountryMusicConnection, TrendKeyword.id == CountryMusicConnection.keyword_id)
            .where(TrendKeyword.detected_at >= cutoff)
            .group_by(TrendKeyword.id)
            .order_by(
                desc(func.count(CountryMusicConnection.id)),  # Keywords with connections first
                desc(TrendKeyword.search_volume)
            )
            .limit(50)
        )
        keyword_rows = keywords_result.all()
        
        # Get story angles - limited to 50 for performance
        angles_result = await db.execute(
            select(StoryAngle)
            .where(StoryAngle.created_at >= cutoff)
            .where(StoryAngle.is_used == False)
            .order_by(desc(StoryAngle.urgency_score), desc(StoryAngle.engagement_potential))
            .limit(50)
        )
        angles = angles_result.scalars().all()
        
        return {
            "trending_keywords": [
                {
                    "id": row.TrendKeyword.id,
                    "keyword": row.TrendKeyword.keyword,
                    "search_volume": row.TrendKeyword.search_volume,
                    "trend_rank": row.TrendKeyword.trend_rank,
                    "connection_count": row.connection_count
                }
                for row in keyword_rows
            ],
            "story_angles": [
                {
                    "id": a.id,
                    "keyword_id": a.keyword_id,
                    "headline": a.headline,
                    "angle_description": a.angle_description,
                    "urgency_score": a.urgency_score,
                    "uniqueness_score": a.uniqueness_score,
                    "engagement_potential": a.engagement_potential,
                    "key_facts": a.key_facts,
                    "suggested_sources": a.suggested_sources,
                    "deep_research_results": a.deep_research_results,
                    "created_at": a.created_at.isoformat(),
                    "is_used": a.is_used
                }
                for a in angles
            ],
            "total_angles": len(angles),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global service instance
story_intelligence_service = StoryIntelligenceService()
