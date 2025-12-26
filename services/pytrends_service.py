"""Google Trends integration using pytrends library (more reliable than Apify)."""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import structlog

logger = structlog.get_logger()

class PyTrendsService:
    """Service for fetching Google Trends data using pytrends library."""
    
    def __init__(self):
        """Initialize PyTrends service."""
        self.tz = 360  # US timezone offset
    
    async def get_trending_searches(
        self,
        keywords: List[str],
        timeframe: str = "now 7-d",
        geo: str = "US"
    ) -> List[Dict]:
        """
        Fetch trending data for keywords.
        
        Args:
            keywords: List of search terms (max 5 at a time for Google API)
            timeframe: Time range (e.g., "now 7-d", "today 1-m")
            geo: Geographic region (e.g., "US", "US-TN")
        
        Returns:
            List of trend data dictionaries
        """
        try:
            # Import pytrends (lazy import to avoid startup issues if not installed)
            from pytrends.request import TrendReq
            
            logger.info(
                "Fetching Google Trends data",
                keywords=keywords[:5],  # Google allows max 5 at once
                timeframe=timeframe,
                geo=geo
            )
            
            # Run in thread pool since pytrends is synchronous
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._fetch_trends_sync,
                keywords[:5],  # Limit to 5
                timeframe,
                geo
            )
            
            return results
            
        except ImportError:
            logger.warning(
                "pytrends not installed. Install with: pip install pytrends"
            )
            return []
        except Exception as e:
            logger.error("Failed to fetch trends", error=str(e))
            return []
    
    def _fetch_trends_sync(
        self,
        keywords: List[str],
        timeframe: str,
        geo: str
    ) -> List[Dict]:
        """Synchronous trends fetching (runs in thread pool)."""
        from pytrends.request import TrendReq
        
        # Initialize pytrends
        pytrends = TrendReq(hl='en-US', tz=self.tz)
        
        results = []
        
        try:
            # Build payload
            pytrends.build_payload(
                kw_list=keywords,
                cat=0,  # All categories
                timeframe=timeframe,
                geo=geo,
                gprop=''  # Web search
            )
            
            # Get interest over time
            interest_df = pytrends.interest_over_time()
            
            if not interest_df.empty:
                # Calculate average interest for each keyword
                for keyword in keywords:
                    if keyword in interest_df.columns:
                        avg_interest = int(interest_df[keyword].mean())
                        max_interest = int(interest_df[keyword].max())
                        
                        # Calculate trend direction (last vs first half)
                        mid_point = len(interest_df) // 2
                        first_half_avg = interest_df[keyword][:mid_point].mean()
                        second_half_avg = interest_df[keyword][mid_point:].mean()
                        trend_change = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
                        
                        results.append({
                            'keyword': keyword,
                            'timeRange': timeframe,
                            'geo_region': geo,
                            'search_volume': avg_interest,
                            'max_volume': max_interest,
                            'change_percent': round(trend_change, 2),
                            'recorded_at': datetime.now(timezone.utc),
                            'source': 'pytrends'
                        })
            
            # Get related queries if available
            try:
                related_queries = pytrends.related_queries()
                for keyword in keywords:
                    if keyword in related_queries and results:
                        # Find matching result
                        for result in results:
                            if result['keyword'] == keyword:
                                top_queries = related_queries[keyword].get('top')
                                if top_queries is not None and not top_queries.empty:
                                    result['related_queries'] = top_queries['query'].head(10).tolist()
                                break
            except:
                pass  # Related queries sometimes fail, that's okay
            
            return results
            
        except Exception as e:
            logger.error("PyTrends sync fetch failed", error=str(e))
            return []


# Singleton instance
pytrends_service = PyTrendsService()

