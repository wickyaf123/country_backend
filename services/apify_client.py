"""Apify client for Google Trends integration."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import logging

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from config import settings

logger = structlog.get_logger()


def parse_search_volume(volume_str) -> int:
    """
    Parse Google Trends search volume strings into numeric values.
    
    Examples:
        "20K+" -> 20000
        "2M+" -> 2000000
        "500+" -> 500
        "5.2K+" -> 5200
    
    Args:
        volume_str: Volume string from Google Trends (can be string or number)
    
    Returns:
        Integer representation of the search volume
    """
    if not volume_str:
        return 0
    
    # If already a number, return it
    if isinstance(volume_str, (int, float)):
        return int(volume_str)
    
    # Remove '+' and whitespace
    volume_str = str(volume_str).replace('+', '').strip().upper()
    
    if not volume_str:
        return 0
    
    try:
        # Handle K (thousands)
        if 'K' in volume_str:
            return int(float(volume_str.replace('K', '')) * 1000)
        
        # Handle M (millions)
        if 'M' in volume_str:
            return int(float(volume_str.replace('M', '')) * 1000000)
        
        # Plain number
        return int(float(volume_str))
    except (ValueError, AttributeError):
        logger.warning(f"Could not parse search volume: {volume_str}")
        return 0


@dataclass
class ApifyRunResult:
    """Result from an Apify actor run."""
    run_id: str
    status: str
    data: List[Dict[str, Any]]
    started_at: datetime
    finished_at: Optional[datetime] = None


@dataclass
class GoogleTrendsData:
    """Processed Google Trends data from Apify."""
    keyword: str
    search_volume: int
    change_percent: Optional[float]
    geo_region: Optional[str]
    related_queries: List[str]
    time_range: str
    recorded_at: datetime
    apify_run_id: str


class ApifyClientError(Exception):
    """Base exception for Apify client errors."""
    pass


class ApifyClient:
    """Client for interacting with Apify REST API."""
    
    # New fast scraper actor ID
    GOOGLE_TRENDS_FAST_SCRAPER = "data_xplorer/google-trends-fast-scraper"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Apify client."""
        self.api_key = api_key or settings.apify_api_key
        if not self.api_key:
            raise ApifyClientError("Apify API key is required")
        
        self.base_url = "https://api.apify.com/v2"
        self.actor_id = settings.apify_actor_id
        self.timeout = settings.apify_timeout_seconds
        self.max_retries = settings.apify_max_retries
        
        # HTTP client configuration
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    async def run_google_trends_fast_trending(
        self,
        country: str = "US",
        timeframe_hours: int = 24,
        use_proxy: bool = True
    ) -> ApifyRunResult:
        """
        Run the fast Google Trends scraper for trending searches.
        
        Based on: https://apify.com/data_xplorer/google-trends-fast-scraper
        
        Args:
            country: Country code (e.g., 'US', 'GB', 'FR')
            timeframe_hours: Time period (4, 24, 48, or 168 hours)
            use_proxy: Whether to use Apify residential proxies
        
        Returns:
            ApifyRunResult with trending searches data
        """
        logger.info(
            "Starting fast Google Trends trending searches",
            country=country,
            timeframe_hours=timeframe_hours
        )
        
        # Validate timeframe
        valid_timeframes = [4, 24, 48, 168]
        if timeframe_hours not in valid_timeframes:
            logger.warning(
                f"Invalid timeframe {timeframe_hours}h, defaulting to 24h",
                valid_timeframes=valid_timeframes
            )
            timeframe_hours = 24
        
        # Prepare actor input
        run_input = {
            "enableTrendingSearches": True,
            "trendingSearchesCountry": country,
            "trendingSearchesTimeframe": str(timeframe_hours),
            "proxyConfiguration": {
                "useApifyProxy": use_proxy
            }
        }
        
        if use_proxy:
            run_input["proxyConfiguration"]["apifyProxyGroups"] = ["RESIDENTIAL"]
        
        try:
            # URL encode the actor ID (replace / with ~)
            actor_id_encoded = self.GOOGLE_TRENDS_FAST_SCRAPER.replace("/", "~")
            response = await self._make_request(
                "POST",
                f"/acts/{actor_id_encoded}/runs",
                json=run_input
            )
            
            run_data = response.json()["data"]
            run_id = run_data["id"]
            
            logger.info("Fast trending scraper run started", run_id=run_id)
            
            # Wait for completion
            result = await self._wait_for_completion(
                run_id, 
                actor_id=actor_id_encoded
            )
            
            # Fetch results
            dataset_items = await self._fetch_dataset_items(result["defaultDatasetId"])
            
            return ApifyRunResult(
                run_id=run_id,
                status=result["status"],
                data=dataset_items,
                started_at=datetime.fromisoformat(result["startedAt"].replace("Z", "+00:00")),
                finished_at=datetime.fromisoformat(result["finishedAt"].replace("Z", "+00:00")) if result.get("finishedAt") else None
            )
            
        except Exception as e:
            logger.error("Failed to run fast trending scraper", error=str(e))
            raise ApifyClientError(f"Actor run failed: {str(e)}")
    
    async def run_google_trends_fast_keywords(
        self,
        keywords: List[str],
        timeframe: str = "today 12-m",
        geo: str = "US",
        fetch_regional_data: bool = False,
        use_proxy: bool = True
    ) -> List[ApifyRunResult]:
        """
        Run the fast Google Trends scraper for keyword analysis.
        Note: This scraper processes one keyword at a time.
        
        Args:
            keywords: List of keywords to analyze
            timeframe: Time period (e.g., 'today 12-m', 'today 3-m', 'now 7-d')
            geo: Country code (e.g., 'US', 'GB') or empty string for worldwide
            fetch_regional_data: Whether to fetch regional interest data
            use_proxy: Whether to use Apify residential proxies
        
        Returns:
            List of ApifyRunResult, one per keyword
        """
        logger.info(
            "Starting fast Google Trends keyword analysis",
            keywords=keywords,
            timeframe=timeframe,
            geo=geo
        )
        
        results = []
        
        for keyword in keywords:
            try:
                # Prepare actor input for single keyword
                run_input = {
                    "enableTrendingSearches": False,
                    "keyword": keyword,
                    "predefinedTimeframe": timeframe,
                    "geo": geo,
                    "fetchRegionalData": fetch_regional_data,
                    "proxyConfiguration": {
                        "useApifyProxy": use_proxy
                    }
                }
                
                if use_proxy:
                    run_input["proxyConfiguration"]["apifyProxyGroups"] = ["RESIDENTIAL"]
                
                # URL encode the actor ID (replace / with ~)
                actor_id_encoded = self.GOOGLE_TRENDS_FAST_SCRAPER.replace("/", "~")
                response = await self._make_request(
                    "POST",
                    f"/acts/{actor_id_encoded}/runs",
                    json=run_input
                )
                
                run_data = response.json()["data"]
                run_id = run_data["id"]
                
                logger.info("Fast keyword scraper run started", run_id=run_id, keyword=keyword)
                
                # Wait for completion
                result = await self._wait_for_completion(
                    run_id, 
                    actor_id=actor_id_encoded
                )
                
                # Fetch results
                dataset_items = await self._fetch_dataset_items(result["defaultDatasetId"])
                
                results.append(ApifyRunResult(
                    run_id=run_id,
                    status=result["status"],
                    data=dataset_items,
                    started_at=datetime.fromisoformat(result["startedAt"].replace("Z", "+00:00")),
                    finished_at=datetime.fromisoformat(result["finishedAt"].replace("Z", "+00:00")) if result.get("finishedAt") else None
                ))
                
            except Exception as e:
                logger.error("Failed to analyze keyword", keyword=keyword, error=str(e))
                # Continue with other keywords
                continue
        
        logger.info(f"Completed keyword analysis for {len(results)}/{len(keywords)} keywords")
        return results
    
    async def run_google_trends_advanced(
        self,
        scrape_type: str = "interest_over_time",
        keywords: List[str] = None,
        geo: str = "US",
        timeframe: str = "today 12-m",
        geo_resolution: str = "COUNTRY",
        inc_low_vol: bool = False,
        trending_hours: int = 24,
        trending_language: str = "en"
    ) -> ApifyRunResult:
        """
        DEPRECATED: Use run_google_trends_fast_trending or run_google_trends_fast_keywords instead.
        
        This method is kept for backward compatibility and now redirects to the new fast scraper.
        """
        logger.warning(
            "run_google_trends_advanced is deprecated, using new fast scraper",
            scrape_type=scrape_type
        )
        
        # Map to new fast scraper based on scrape_type
        if scrape_type == "trending_now":
            # Map trending_hours to valid timeframe
            timeframe_hours = 24
            if trending_hours <= 4:
                timeframe_hours = 4
            elif trending_hours <= 24:
                timeframe_hours = 24
            elif trending_hours <= 48:
                timeframe_hours = 48
            else:
                timeframe_hours = 168
            
            return await self.run_google_trends_fast_trending(
                country=geo,
                timeframe_hours=timeframe_hours,
                use_proxy=True
            )
        else:
            # For keyword-based scrapes, run for first keyword only
            if keywords and len(keywords) > 0:
                results = await self.run_google_trends_fast_keywords(
                    keywords=[keywords[0]],
                    timeframe=timeframe,
                    geo=geo,
                    fetch_regional_data=(scrape_type == "interest_by_region"),
                    use_proxy=True
                )
                return results[0] if results else None
            else:
                raise ApifyClientError("Keywords required for non-trending scrape types")
    
    async def _wait_for_completion(self, run_id: str, poll_interval: int = 10, actor_id: str = None) -> Dict[str, Any]:
        """Wait for actor run to complete."""
        logger.info("Waiting for actor run completion", run_id=run_id)
        
        actor_id = actor_id or self.actor_id
        max_wait_time = 600  # 10 minutes (new scraper is faster)
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            response = await self._make_request("GET", f"/acts/{actor_id}/runs/{run_id}")
            run_data = response.json()["data"]
            
            status = run_data["status"]
            logger.debug("Actor run status", run_id=run_id, status=status)
            
            if status in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"]:
                if status != "SUCCEEDED":
                    raise ApifyClientError(f"Actor run {status.lower()}: {run_id}")
                return run_data
            
            await asyncio.sleep(poll_interval)
            elapsed_time += poll_interval
        
        raise ApifyClientError(f"Actor run timed out after {max_wait_time} seconds: {run_id}")
    
    async def _fetch_dataset_items(self, dataset_id: str) -> List[Dict[str, Any]]:
        """Fetch items from a dataset."""
        logger.info("Fetching dataset items", dataset_id=dataset_id)
        
        try:
            response = await self._make_request("GET", f"/datasets/{dataset_id}/items")
            return response.json()
        except Exception as e:
            logger.error("Failed to fetch dataset items", dataset_id=dataset_id, error=str(e))
            raise ApifyClientError(f"Failed to fetch dataset: {str(e)}")
    
    async def abort_actor_run(self, run_id: str) -> bool:
        """Abort a running actor."""
        logger.info("Aborting actor run", run_id=run_id)
        
        try:
            response = await self._make_request(
                "POST",
                f"/acts/{self.actor_id}/runs/{run_id}/abort"
            )
            
            result = response.json()
            logger.info("Actor run aborted", run_id=run_id, status=result.get("data", {}).get("status"))
            return True
            
        except Exception as e:
            logger.error("Failed to abort actor run", run_id=run_id, error=str(e))
            raise ApifyClientError(f"Failed to abort actor run: {str(e)}")
    
    async def get_actor_run_status(self, run_id: str) -> Dict[str, Any]:
        """Get the status of an actor run."""
        try:
            response = await self._make_request("GET", f"/acts/{self.actor_id}/runs/{run_id}")
            return response.json()["data"]
        except Exception as e:
            logger.error("Failed to get actor run status", run_id=run_id, error=str(e))
            raise ApifyClientError(f"Failed to get status: {str(e)}")
    
    async def list_actor_runs(
        self,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List actor runs, optionally filtered by status."""
        try:
            params = {"limit": limit}
            if status:
                params["status"] = status
            
            response = await self._make_request(
                "GET",
                f"/acts/{self.actor_id}/runs",
                params=params
            )
            return response.json()["data"]["items"]
        except Exception as e:
            logger.error("Failed to list actor runs", error=str(e))
            raise ApifyClientError(f"Failed to list runs: {str(e)}")
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Rate limited, retrying",
                        attempt=attempt,
                        wait_time=wait_time
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise ApifyClientError(f"HTTP {e.response.status_code}: {e.response.text}")
                
            except httpx.RequestError as e:
                if attempt == self.max_retries:
                    raise ApifyClientError(f"Request failed after {self.max_retries} retries: {str(e)}")
                
                wait_time = 2 ** attempt
                logger.warning(
                    "Request failed, retrying",
                    attempt=attempt,
                    wait_time=wait_time,
                    error=str(e)
                )
                await asyncio.sleep(wait_time)
        
        raise ApifyClientError("Max retries exceeded")
    
    def transform_advanced_trends_data(
        self,
        apify_result: ApifyRunResult
    ) -> List[GoogleTrendsData]:
        """Transform advanced actor results with enhanced data structure."""
        trends_data = []
        
        for item in apify_result.data:
            try:
                scrape_type = item.get("scrape_type", "")
                data = item.get("data", [])
                error = item.get("error", False)
                
                if error:
                    logger.error("Apify actor returned error", error_message=item.get("error_message"))
                    continue
                
                # Handle different scrape types
                if scrape_type == "trending_now":
                    # Process trending searches
                    for trend_item in data:
                        keyword = trend_item.get("keyword", "")
                        # Parse search volume from string format (e.g., "20K+", "2M+")
                        raw_volume = trend_item.get("approx_traffic", 0)
                        search_volume = parse_search_volume(raw_volume)
                        
                        logger.debug(
                            "Parsed search volume",
                            keyword=keyword,
                            raw_volume=raw_volume,
                            parsed_volume=search_volume
                        )
                        
                        trends_data.append(GoogleTrendsData(
                            keyword=keyword,
                            search_volume=search_volume,
                            change_percent=None,
                            geo_region=trend_item.get("geo", ""),
                            related_queries=trend_item.get("topic_names", []),
                            time_range=f"{trend_item.get('hours', 24)}h",
                            recorded_at=datetime.now(timezone.utc),
                            apify_run_id=apify_result.run_id
                        ))
                
                elif scrape_type == "interest_over_time":
                    # Process time series data
                    for time_data in data:
                        keyword = time_data.get("keyword", "")
                        values = time_data.get("value", [])
                        
                        # Calculate average and trend
                        if values:
                            avg_volume = sum(values) / len(values)
                            change_percent = ((values[-1] - values[0]) / values[0] * 100) if values[0] > 0 else 0
                            
                            trends_data.append(GoogleTrendsData(
                                keyword=keyword,
                                search_volume=int(avg_volume),
                                change_percent=change_percent,
                                geo_region=time_data.get("geo", ""),
                                related_queries=[],
                                time_range=time_data.get("timeframe", ""),
                                recorded_at=datetime.now(timezone.utc),
                                apify_run_id=apify_result.run_id
                            ))
                
                elif scrape_type == "related_queries":
                    # Process related queries
                    for query_data in data:
                        keyword = query_data.get("keyword", "")
                        top_queries = query_data.get("top", [])
                        rising_queries = query_data.get("rising", [])
                        
                        all_related = []
                        all_related.extend([q.get("query", "") for q in top_queries if isinstance(q, dict)])
                        all_related.extend([q.get("query", "") for q in rising_queries if isinstance(q, dict)])
                        
                        trends_data.append(GoogleTrendsData(
                            keyword=keyword,
                            search_volume=0,  # Not provided for related queries
                            change_percent=None,
                            geo_region="",
                            related_queries=all_related[:20],  # Top 20 related
                            time_range="",
                            recorded_at=datetime.now(timezone.utc),
                            apify_run_id=apify_result.run_id
                        ))
                
                elif scrape_type == "interest_by_region":
                    # Process geographic data
                    for geo_data in data:
                        keyword = geo_data.get("keyword", "")
                        region = geo_data.get("geoName", "")
                        value = geo_data.get("value", [0])[0] if isinstance(geo_data.get("value"), list) else geo_data.get("value", 0)
                        
                        trends_data.append(GoogleTrendsData(
                            keyword=keyword,
                            search_volume=value,
                            change_percent=None,
                            geo_region=region,
                            related_queries=[],
                            time_range="",
                            recorded_at=datetime.now(timezone.utc),
                            apify_run_id=apify_result.run_id
                        ))
            
            except Exception as e:
                logger.error("Failed to transform advanced Apify item", item=item, error=str(e))
                continue
        
        logger.info(f"Transformed {len(trends_data)} trend items from advanced actor")
        return trends_data
    
    def transform_fast_trending_data(
        self,
        apify_result: ApifyRunResult
    ) -> List[GoogleTrendsData]:
        """
        Transform data from the new fast trending scraper.
        
        Expected format:
        {
            "geo": "US",
            "language": "en-US",
            "timeframe_hours": 24,
            "trending_searches": [
                {
                    "rank": 1,
                    "term": "keyword",
                    "trend_volume": "500k+",
                    "trend_volume_formatted": 500000,
                    "related_terms": ["term1", "term2"]
                }
            ]
        }
        """
        trends_data = []
        
        for item in apify_result.data:
            try:
                geo = item.get("geo", "US")
                timeframe_hours = item.get("timeframe_hours", 24)
                trending_searches = item.get("trending_searches", [])
                
                logger.info(
                    f"Processing {len(trending_searches)} trending searches",
                    geo=geo,
                    timeframe_hours=timeframe_hours
                )
                
                for trend in trending_searches:
                    keyword = trend.get("term", "")
                    
                    # Use formatted volume if available, otherwise parse string
                    if "trend_volume_formatted" in trend:
                        search_volume = trend["trend_volume_formatted"]
                    else:
                        raw_volume = trend.get("trend_volume", "0")
                        search_volume = parse_search_volume(raw_volume)
                    
                    related_terms = trend.get("related_terms", [])
                    
                    logger.debug(
                        "Parsed trending search",
                        keyword=keyword,
                        search_volume=search_volume,
                        rank=trend.get("rank")
                    )
                    
                    trends_data.append(GoogleTrendsData(
                        keyword=keyword,
                        search_volume=search_volume,
                        change_percent=None,
                        geo_region=geo,
                        related_queries=related_terms,
                        time_range=f"{timeframe_hours}h",
                        recorded_at=datetime.now(timezone.utc),
                        apify_run_id=apify_result.run_id
                    ))
                
            except Exception as e:
                logger.error("Failed to transform trending item", item=item, error=str(e))
                continue
        
        logger.info(f"Transformed {len(trends_data)} trending searches")
        return trends_data
    
