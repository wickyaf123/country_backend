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
        Run the advanced Google Trends actor with multiple scrape types.
        
        Based on: https://apify.com/qp6mKSScYoutYqCOa/google-trends-scraper
        
        Args:
            scrape_type: Type of scrape (trending_now, interest_over_time, related_queries, interest_by_region)
            keywords: List of keywords to search for
            geo: Geographic region (e.g., 'US', 'GB')
            timeframe: Time range for trends (e.g., 'today 12-m')
            geo_resolution: Geographic resolution (COUNTRY, REGION, DMA, CITY)
            inc_low_vol: Include low-volume regions
            trending_hours: Hours for trending searches (1-191)
            trending_language: Language for trending searches
        """
        logger.info(
            "Starting advanced Google Trends actor run",
            scrape_type=scrape_type,
            keywords=keywords,
            geo=geo
        )
        
        # Prepare actor input for the new actor
        run_input = {
            "scrape_type": scrape_type,
            "keywords": keywords or [],
            "gprop": "web",
            "timeframe_type": "predefined",
            "predefined_timeframe": timeframe,
            "custom_timeframe": "",
            "geo_selection_type": "Common Countries",
            "common_geo": geo,
            "custom_geo_code": "",
            "geo_resolution": geo_resolution,
            "inc_low_vol": inc_low_vol,
            "trending_language": trending_language,
            "trending_hours": trending_hours,
            "proxyConfiguration": {}
        }
        
        try:
            # Use the new actor ID
            new_actor_id = "qp6mKSScYoutYqCOa"
            
            response = await self._make_request(
                "POST",
                f"/acts/{new_actor_id}/runs",
                json=run_input
            )
            
            run_data = response.json()["data"]
            run_id = run_data["id"]
            
            logger.info("Advanced actor run started", run_id=run_id, scrape_type=scrape_type)
            
            # Wait for completion
            result = await self._wait_for_completion(run_id, actor_id=new_actor_id)
            
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
            logger.error("Failed to run advanced Google Trends actor", error=str(e))
            raise ApifyClientError(f"Actor run failed: {str(e)}")
    
    async def run_trending_searches(
        self,
        timeframe: str = "24",
        country: str = "US"
    ) -> ApifyRunResult:
        """
        Run trending searches using the FAST Google Trends actor.
        
        Args:
            timeframe: Hours for trending searches ("4", "24", "48", "168")
            country: Country code (e.g., "US")
        
        Returns:
            ApifyRunResult with ALL trending keywords for the timeframe
        """
        logger.info(
            "Starting trending searches with FAST actor",
            timeframe=timeframe,
            country=country
        )
        
        run_input = {
            "enableTrendingSearches": True,
            "trendingSearchesCountry": country,
            "trendingSearchesTimeframe": timeframe,
            "proxyConfiguration": {"useApifyProxy": True}
        }
        
        try:
            response = await self._make_request(
                "POST",
                f"/acts/{self.actor_id}/runs",
                json=run_input
            )
            
            run_data = response.json()["data"]
            run_id = run_data["id"]
            
            logger.info("Trending searches run started", run_id=run_id, timeframe=timeframe)
            
            result = await self._wait_for_completion(run_id, actor_id=self.actor_id)
            dataset_items = await self._fetch_dataset_items(result["defaultDatasetId"])
            
            return ApifyRunResult(
                run_id=run_id,
                status=result["status"],
                data=dataset_items,
                started_at=datetime.fromisoformat(result["startedAt"].replace("Z", "+00:00")),
                finished_at=datetime.fromisoformat(result["finishedAt"].replace("Z", "+00:00")) if result.get("finishedAt") else None
            )
            
        except Exception as e:
            logger.error("Failed to run trending searches", error=str(e))
            raise ApifyClientError(f"Trending searches failed: {str(e)}")
    
    async def _wait_for_completion(self, run_id: str, poll_interval: int = 10, actor_id: str = None) -> Dict[str, Any]:
        """Wait for actor run to complete."""
        logger.info("Waiting for actor run completion", run_id=run_id)
        
        actor_id = actor_id or self.actor_id
        max_wait_time = 900  # 15 minutes (actor takes 6-8 minutes typically)
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
                        search_volume = trend_item.get("approx_traffic", 0)
                        
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
    
    def transform_trending_searches_data(
        self,
        apify_result: ApifyRunResult
    ) -> List[GoogleTrendsData]:
        """Transform FAST actor trending searches results."""
        trends_data = []
        
        for item in apify_result.data:
            try:
                trending_searches = item.get("trending_searches", [])
                geo = item.get("geo", "US")
                timeframe_hours = item.get("timeframe_hours", 24)
                
                for trend_item in trending_searches:
                    keyword = trend_item.get("term", "")
                    
                    # Parse volume (e.g., "500k+" -> 500000)
                    volume_formatted = trend_item.get("trend_volume_formatted", 0)
                    search_volume = volume_formatted if isinstance(volume_formatted, int) else 0
                    
                    related_terms = trend_item.get("related_terms", [])
                    
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
                logger.error("Failed to transform trending search item", item=item, error=str(e))
                continue
        
        logger.info(f"Transformed {len(trends_data)} trending keywords from FAST actor")
        return trends_data
    
