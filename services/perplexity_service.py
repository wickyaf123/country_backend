"""Perplexity AI service for web search + AI analysis."""

import httpx
import structlog
from typing import List, Dict, Any, Optional, Literal
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
from datetime import datetime, timedelta

from config import settings

logger = structlog.get_logger()


class PerplexityRateLimiter:
    """Rate limiter for Perplexity API to respect RPM limits."""
    
    def __init__(self):
        self.request_times: Dict[str, List[datetime]] = {
            "sonar-reasoning-pro": [],
            "sonar-deep-research": []
        }
        self.limits = {
            "sonar-reasoning-pro": 50,  # 50 RPM
            "sonar-deep-research": 10   # 10 RPM
        }
        self.lock = asyncio.Lock()
    
    async def wait_if_needed(self, model: str):
        """Wait if we've hit the rate limit for this model."""
        async with self.lock:
            now = datetime.now()
            one_minute_ago = now - timedelta(minutes=1)
            
            # Clean up old requests
            self.request_times[model] = [
                t for t in self.request_times[model] 
                if t > one_minute_ago
            ]
            
            # Check if we need to wait
            if len(self.request_times[model]) >= self.limits[model]:
                # Calculate wait time
                oldest_request = self.request_times[model][0]
                wait_until = oldest_request + timedelta(minutes=1)
                wait_seconds = (wait_until - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.warning(
                        "Rate limit reached, waiting",
                        model=model,
                        wait_seconds=wait_seconds,
                        requests_in_window=len(self.request_times[model])
                    )
                    await asyncio.sleep(wait_seconds)
                    # Clean up again after waiting
                    now = datetime.now()
                    one_minute_ago = now - timedelta(minutes=1)
                    self.request_times[model] = [
                        t for t in self.request_times[model] 
                        if t > one_minute_ago
                    ]
            
            # Record this request
            self.request_times[model].append(now)


class PerplexityService:
    """Client for Perplexity AI API - combines web search with AI reasoning."""
    
    ModelType = Literal["sonar-reasoning-pro", "sonar-deep-research"]
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.perplexity_api_key
        if not self.api_key:
            logger.warning("Perplexity API key not configured")
        
        self.base_url = "https://api.perplexity.ai"
        # Default to reasoning-pro for general use (50 RPM, faster)
        self.default_model = "sonar-reasoning-pro"
        self.rate_limiter = PerplexityRateLimiter()
        
        # Semaphores to limit concurrent requests and prevent burst traffic
        # This works together with rate_limiter to prevent race conditions
        self.semaphores = {
            "sonar-reasoning-pro": asyncio.Semaphore(8),  # Max 8 concurrent for 50 RPM limit
            "sonar-deep-research": asyncio.Semaphore(3)   # Max 3 concurrent for 10 RPM limit (on-demand use)
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def search_and_analyze(
        self,
        query: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        model: Optional[ModelType] = None,
        deep_research: bool = False
    ) -> Dict[str, Any]:
        """
        Perform web search + AI analysis in one call.
        
        Args:
            query: The question/search query
            system_prompt: Optional system instructions
            temperature: Randomness (0.0-1.0, lower = more factual)
            model: Override model selection ("sonar-reasoning-pro" or "sonar-deep-research")
            deep_research: If True, uses deep-research model (slower, more thorough)
            
        Returns:
            Dict with:
                - 'content': AI response text
                - 'citations': List of source URLs used
                - 'model_used': Which model was used
        """
        if not self.api_key:
            raise ValueError("Perplexity API key required")
        
        # Determine which model to use
        if model:
            selected_model = model
        elif deep_research:
            selected_model = "sonar-deep-research"
        else:
            selected_model = self.default_model
        
        # Acquire semaphore to limit concurrent requests (prevents burst traffic)
        async with self.semaphores[selected_model]:
            # Wait if we need to respect rate limits
            await self.rate_limiter.wait_if_needed(selected_model)
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": query})
            
            payload = {
                "model": selected_model,
                "messages": messages,
                "temperature": temperature,
                "return_citations": True,
                "return_images": False
            }
            
            # Adjust max_tokens based on model
            if selected_model == "sonar-deep-research":
                payload["max_tokens"] = 5000  # Deep research needs more tokens
            else:
                payload["max_tokens"] = 3000
            
            try:
                # Longer timeout for deep research
                timeout = 120.0 if selected_model == "sonar-deep-research" else 60.0
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json=payload
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    result = {
                        "content": data["choices"][0]["message"]["content"],
                        "citations": data.get("citations", []),
                        "model_used": selected_model
                    }
                    
                    logger.info(
                        "Perplexity search complete",
                        model=selected_model,
                        query_length=len(query),
                        response_length=len(result["content"]),
                        citations_count=len(result["citations"])
                    )
                    
                    return result
                    
            except httpx.HTTPStatusError as e:
                # Get the actual error response body
                try:
                    error_body = e.response.json()
                    error_msg = error_body.get("error", {}).get("message", str(error_body))
                except:
                    error_body = e.response.text
                    error_msg = error_body
                
                logger.error(
                    "Perplexity API HTTP error",
                    status_code=e.response.status_code,
                    error=str(e),
                    error_body=error_body,
                    model=selected_model
                )
                
                # Provide helpful error message
                if e.response.status_code == 404:
                    raise ValueError(f"Perplexity model '{selected_model}' not found. This model may not be available with your API plan. Error: {error_msg}")
                elif e.response.status_code == 401:
                    raise ValueError("Perplexity API authentication failed. Check your API key.")
                elif e.response.status_code == 429:
                    raise ValueError("Perplexity API rate limit exceeded. Please try again later.")
                else:
                    raise ValueError(f"Perplexity API error {e.response.status_code}: {error_msg}")
            except Exception as e:
                logger.error("Perplexity API call failed", error=str(e), model=selected_model)
                raise


# Global instance
perplexity_service = PerplexityService()

