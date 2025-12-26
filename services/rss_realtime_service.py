"""Real-time RSS scraper for Story Intelligence - Simplified with hardcoded sources."""

import asyncio
import feedparser
import re
import json
from datetime import datetime, timezone
from typing import List, Dict, Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from models.story_intelligence import RSSStoryLead
from services.perplexity_service import perplexity_service

logger = structlog.get_logger()


class RSSRealtimeService:
    """
    Real-time RSS scraper specifically for Story Intelligence.
    Continuously monitors RSS feeds and matches with trending keywords.
    """
    
    def __init__(self):
        self.perplexity_service = perplexity_service
        # Use keywords from config
        self.country_music_keywords = settings.country_music_keywords
        
        # Hardcoded important country music RSS feeds
        self.default_sources = [
            {"name": "Taste of Country", "url": "https://tasteofcountry.com/feed/"},
            {"name": "The Boot", "url": "https://theboot.com/feed/"},
            {"name": "Rolling Stone Country", "url": "https://www.rollingstone.com/music/music-country/feed/"},
            {"name": "Whiskey Riff", "url": "https://www.whiskeyriff.com/feed/"},
            {"name": "Country Now", "url": "https://countrynow.com/feed/"},
            {"name": "Sounds Like Nashville", "url": "https://www.soundslikenashville.com/feed/"},
            {"name": "MusicRow", "url": "https://musicrow.com/feed/"},
            {"name": "Billboard Country", "url": "https://www.billboard.com/c/music/country/feed/"},
            {"name": "Saving Country Music", "url": "https://www.savingcountrymusic.com/feed/"},
            {"name": "Music Mayhem", "url": "https://musicmayhemmagazine.com/feed/"},
            {"name": "Country Rebel", "url": "https://countryrebel.com/feed/"}
        ]
    
    async def scrape_rss_for_intelligence(
        self,
        db: AsyncSession,
        trending_keywords: List[str]
    ) -> List[RSSStoryLead]:
        """
        Scrape RSS feeds and look for stories related to trending keywords.
        """
        from models.story_intelligence import TrendKeyword
        
        logger.info("Starting RSS scrape for story intelligence")
        
        # Get keyword objects with IDs for matching
        keyword_result = await db.execute(
            select(TrendKeyword)
            .where(TrendKeyword.keyword.in_(trending_keywords))
        )
        keyword_objects = {kw.keyword.lower(): kw.id for kw in keyword_result.scalars().all()}
        
        logger.info(f"Scraping {len(self.default_sources)} default RSS sources, matching against {len(keyword_objects)} keywords")
        
        all_leads = []
        
        # Scrape each source
        for source in self.default_sources:
            try:
                leads = await self._scrape_single_source(
                    db, source, trending_keywords, keyword_objects
                )
                all_leads.extend(leads)
            except Exception as e:
                logger.error(
                    "RSS source scrape failed",
                    source=source["name"],
                    error=str(e)
                )
        
        logger.info(f"Found {len(all_leads)} RSS story leads")
        return all_leads
    
    async def _scrape_single_source(
        self,
        db: AsyncSession,
        source: Dict[str, str],
        trending_keywords: List[str],
        keyword_id_map: Dict[str, str]
    ) -> List[RSSStoryLead]:
        """Scrape a single RSS source."""
        try:
            # Parse RSS feed
            feed = await asyncio.to_thread(feedparser.parse, source["url"])
            
            leads = []
            
            for entry in feed.entries[:20]:  # Last 20 entries
                title = entry.get("title", "")
                link = entry.get("link", "")
                published = entry.get("published_parsed")
                
                # Convert published date
                if published:
                    pub_date = datetime(*published[:6], tzinfo=timezone.utc)
                else:
                    pub_date = datetime.now(timezone.utc)
                
                # Extract keywords and check relevance
                analysis = await self._analyze_rss_entry(
                    title, trending_keywords, keyword_id_map
                )
                
                if analysis["is_relevant"]:
                    lead = RSSStoryLead(
                        title=title,
                        url=link,
                        source_name=source["name"],
                        published_at=pub_date,
                        extracted_keywords={"keywords": analysis["keywords"]},
                        country_music_relevance=analysis["relevance_score"],
                        matched_trend_keyword_id=analysis.get("matched_keyword_id")
                    )
                    db.add(lead)
                    leads.append(lead)
            
            await db.commit()
            return leads
            
        except Exception as e:
            logger.error(
                "Failed to scrape RSS source",
                source=source["name"],
                error=str(e)
            )
            return []
    
    async def _analyze_rss_entry(
        self,
        title: str,
        trending_keywords: List[str],
        keyword_id_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Analyze RSS entry for country music relevance and keyword matches.
        Uses a two-stage approach:
        1. Improved direct matching with regex and expanded keyword list.
        2. Perplexity AI fallback for complex or indirect connections.
        """
        title_lower = title.lower()
        
        # 1. IMPROVED DIRECT MATCHING
        matched_keywords = []
        matched_keyword_id = None
        
        # Check against trending keywords first (prioritize them)
        for kw in trending_keywords:
            # Use regex for word boundaries to avoid partial matches
            if re.search(rf"\b{re.escape(kw.lower())}\b", title_lower):
                matched_keywords.append(kw)
                if not matched_keyword_id:
                    matched_keyword_id = keyword_id_map.get(kw.lower())
        
        # Check against general country music keywords/artists
        direct_country_match = False
        for kw in self.country_music_keywords:
            if re.search(rf"\b{re.escape(kw.lower())}\b", title_lower):
                direct_country_match = True
                break
        
        if matched_keywords or direct_country_match:
            return {
                "is_relevant": True,
                "keywords": matched_keywords,
                "relevance_score": 1.0 if direct_country_match else 0.8,
                "matched_keyword_id": matched_keyword_id
            }
        
        # 2. PERPLEXITY FALLBACK
        # Only use AI for potential connections in top 20 trending keywords
        if len(trending_keywords) > 0:
            # Identify keywords that might have words in common with the title
            potential_keywords = [
                kw for kw in trending_keywords[:20] 
                if any(len(word) > 3 and word.lower() in title_lower for word in kw.split())
            ]
            
            if potential_keywords:
                prompt = f"""Analyze this news headline for its connection to country music and specific trending topics.

Headline: {title}
Trending Topics: {', '.join(potential_keywords)}

Task:
1. Determine if this headline is related to country music (directly or indirectly).
2. Check if it connects to any of the listed trending topics.
3. Provide a relevance score (0.0 to 1.0).
4. Identify which specific country music entities (artists, venues, labels) are involved.

Return ONLY a RAW JSON object (no markdown) with this structure:
{{
    "is_relevant": true/false,
    "relevance_score": 0.0-1.0,
    "extracted_keywords": ["keyword1", "keyword2"],
    "connection_explanation": "brief explanation",
    "entities": ["Artist Name"]
}}"""
                
                try:
                    # Use sonar-reasoning-pro for fast but smart analysis
                    result = await self.perplexity_service.search_and_analyze(
                        query=prompt,
                        temperature=0.1
                    )
                    
                    # Parse JSON from content
                    content = result["content"]
                    # Clean up markdown if AI includes it
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    
                    response = json.loads(content)
                    
                    # Map matched keywords to IDs
                    extracted_kws = response.get("extracted_keywords", [])
                    final_matched_id = None
                    for kw in extracted_kws:
                        kw_id = keyword_id_map.get(kw.lower())
                        if kw_id:
                            final_matched_id = kw_id
                            break
                    
                    return {
                        "is_relevant": response.get("is_relevant", False),
                        "keywords": extracted_kws,
                        "relevance_score": response.get("relevance_score", 0.0),
                        "matched_keyword_id": final_matched_id
                    }
                except Exception as e:
                    logger.error("Perplexity RSS analysis failed", error=str(e), title=title)
        
        return {
            "is_relevant": False,
            "keywords": [],
            "relevance_score": 0.0,
            "matched_keyword_id": None
        }


# Global service instance
rss_realtime_service = RSSRealtimeService()
