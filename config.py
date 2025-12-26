"""Configuration management for Country Rebel Story Intelligence System."""

import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings - Story Intelligence focused."""
    
    # Database - Supabase PostgreSQL (required)
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@db.example.supabase.co:5432/postgres",
        description="Supabase PostgreSQL connection URL"
    )
    
    # Supabase Configuration
    supabase_url: str | None = Field(default=None, description="Supabase project URL")
    supabase_anon_key: str | None = Field(default=None, description="Supabase anon/public key")
    supabase_service_key: str | None = Field(default=None, description="Supabase service role key")
    
    # Core API Keys (Required for Story Intelligence)
    openai_api_key: str | None = Field(default=None, description="OpenAI API key for story angle generation")
    openai_model: str = Field(default="gpt-4-turbo-preview", description="OpenAI model to use")
    openai_temperature: float = Field(default=0.7, description="Temperature for OpenAI API calls (0.0-2.0)")
    openai_max_tokens: int = Field(default=4000, description="Maximum tokens for OpenAI responses")
    openai_timeout: int = Field(default=60, description="Timeout for OpenAI API calls in seconds")
    
    perplexity_api_key: str | None = Field(default=None, description="Perplexity AI API key for connection analysis")
    apify_api_key: str | None = Field(default=None, description="Apify API key for Google Trends integration")
    apify_actor_id: str = Field(default="qp6mKSScYoutYqCOa", description="Apify Google Trends actor ID")
    apify_timeout_seconds: int = Field(default=300, description="Timeout for Apify API calls in seconds")
    apify_max_retries: int = Field(default=3, description="Maximum retries for Apify API calls")
    
    # Cache Configuration (Optional - Redis)
    redis_url: str | None = Field(default=None, description="Redis connection URL for caching")
    cache_default_ttl: int = Field(default=3600, description="Default cache TTL in seconds")
    
    # Application Settings
    app_base_url: str = Field(default="http://localhost:8000", description="Base URL for the application")
    app_port: int = Field(default=8000, description="Port to run the application on")
    app_host: str = Field(default="0.0.0.0", description="Host to bind the application to")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Security
    secret_key: str = Field(
        default="change-this-in-production-use-a-secure-random-key",
        description="Secret key for security features"
    )
    
    # Google Trends Keywords for Story Intelligence
    # Top 100 optimized keywords for country music trend detection
    country_music_keywords: List[str] = Field(
        default=[
            # Top Trending Artists 2024-2025
            "Morgan Wallen", "Luke Combs", "Zach Bryan", "Jelly Roll", "Chris Stapleton",
            "Lainey Wilson", "Cody Johnson", "Kane Brown", "Bailey Zimmerman", "Parker McCollum",
            "Tyler Childers", "Jordan Davis", "Riley Green", "Megan Moroney", "Nate Smith",
            "Tucker Wetmore", "Shaboozey", "Ella Langley", "Post Malone country", "Beyonce country",
            "Kelsea Ballerini", "Miranda Lambert", "Carrie Underwood", "Keith Urban", "Blake Shelton",
            "Jason Aldean", "Eric Church", "Dan + Shay", "Old Dominion", "Zac Brown Band",
            
            # High-Value Discovery Keywords
            "country music 2025", "new country songs", "country songs 2025", "top country songs",
            "country music TikTok", "country music hits", "best country songs", "country playlist",
            "country music festivals", "CMA awards", "ACM awards", "Grand Ole Opry",
            "Stagecoach festival", "country music news", "country radio", "country concerts",
            "Nashville", "country music videos", "country breakup songs", "country love songs",
            
            # Legends & Icons
            "Dolly Parton", "Willie Nelson", "Garth Brooks", "Johnny Cash", "George Strait",
            "Reba McEntire", "Shania Twain", "Alan Jackson", "Tim McGraw", "Faith Hill",
            "Kenny Chesney", "Brooks & Dunn", "Toby Keith", "Brad Paisley", "Vince Gill",
            
            # Subgenres & Movements
            "Texas country", "red dirt country", "outlaw country", "country pop",
            "bro country", "Americana", "bluegrass", "honky tonk",
            "stadium country", "indie country",
            
            # Trending Topics & Events
            "CMA Fest", "country music awards", "country summer tour", "country music charts",
            "Billboard country", "country radio countdown", "country music streaming",
            "country music podcast", "country music TikTok viral", "country music duets",
            
            # Viral Songs & Phenomena
            "I Had Some Help", "A Bar Song Tipsy", "Wasted on You", "Fast Car country",
            "Rich Men North of Richmond", "Something in the Orange", "Last Night Morgan Wallen",
            "You Proof", "One Thing At A Time", "Tennessee Orange", "Sand in My Boots",
            "Burn It Down", "Thinking Bout Me", "Need a Favor", "World on Fire"
        ],
        description="100 optimized Google Trends keywords for country music"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env that aren't in the model


# Global settings instance
settings = Settings()
