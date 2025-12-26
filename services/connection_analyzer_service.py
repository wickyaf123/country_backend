"""Multi-degree connection analyzer for Story Intelligence."""

from typing import List, Dict, Any
import structlog

logger = structlog.get_logger()


class ConnectionAnalyzerService:
    """
    Analyzes 1st, 2nd, and 3rd degree connections from keywords to country music.
    
    Uses Perplexity AI with comprehensive single-query approach for maximum efficiency.
    """
    
    async def find_country_music_connections(
        self,
        keyword: str,
        deep_research: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find multi-degree connections with ONE comprehensive query.
        
        Uses Perplexity AI to search all 3 degrees simultaneously:
        - Degree 1: Direct country music connections (artists, venues, labels)
        - Degree 2: One step removed (media, social, festivals)
        - Degree 3: Cultural/lifestyle connections (values, business, patriotic)
        
        Args:
            keyword: The keyword to analyze
            deep_research: If True, uses sonar-deep-research model (slower, more thorough)
        
        Returns:
            List of connections with degree, type, entity, description, confidence,
            connection chain, and evidence.
        """
        logger.info(
            "Finding country music connections (comprehensive single query)", 
            keyword=keyword,
            deep_research_mode=deep_research
        )
        
        try:
            # Execute comprehensive search
            all_connections = await self._search_comprehensive_connections(
                keyword=keyword, 
                deep_research=deep_research
            )
            
            # Add connection chains for visualization
            for conn in all_connections:
                conn['connection_chain'] = self._format_connection_chain(keyword, conn)
            
            # Sort by confidence score
            all_connections.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            
            logger.info(
                "Connection analysis complete",
                keyword=keyword,
                total_queries=1,
                connections_found=len(all_connections),
                degrees_found={
                    1: len([c for c in all_connections if c['degree'] == 1]),
                    2: len([c for c in all_connections if c['degree'] == 2]),
                    3: len([c for c in all_connections if c['degree'] == 3])
                }
            )
            
            return all_connections
            
        except Exception as e:
            logger.error("Connection analysis failed", keyword=keyword, error=str(e))
            return []
    
    def _format_connection_chain(self, keyword: str, connection: Dict) -> str:
        """
        Format connection chain for visualization.
        Example: "Super Bowl → Carrie Underwood → Country Music"
        """
        degree = connection.get('degree', 1)
        entity = connection.get('entity', 'Unknown')
        
        if degree == 1:
            return f"{keyword} → {entity} (Country Music)"
        elif degree == 2:
            return f"{keyword} → {entity} → Country Music"
        else:  # degree 3
            return f"{keyword} → [Cultural/Lifestyle] → {entity} → Country Music"
    
    async def _search_comprehensive_connections(
        self,
        keyword: str,
        deep_research: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Single comprehensive query covering all angles and degrees.
        Much faster than 9 separate queries (v2 approach).
        
        Searches for all connection types in one Perplexity call:
        - Degree 1: Direct artist/venue/label connections
        - Degree 2: Media, social, festival connections
        - Degree 3: Cultural, lifestyle, business, patriotic connections
        
        Args:
            keyword: The keyword to analyze
            deep_research: If True, uses sonar-deep-research model
        
        Returns:
            List of connections across all degrees
        """
        from services.perplexity_service import perplexity_service
        from datetime import datetime
        import json
        
        current_year = datetime.now().year
        
        # Comprehensive system prompt covering all connection types
        system_prompt = f"""You are a JSON API that finds ALL country music connections in one comprehensive search.

Return ONLY raw JSON (no markdown, no code blocks, no think tags).

SEARCH ALL 3 DEGREES simultaneously:

**DEGREE 1** (Direct country music):
- Artists, labels, venues, Billboard charts
- Grand Ole Opry, Nashville locations (Ryman, Bluebird Cafe, Lower Broadway)
- Recent collaborations, duets, songwriting
- CMA/ACM/CMT awards appearances

**DEGREE 2** (One step removed):
- Media appearances (Bobby Bones, CMT, GAC, podcasts, Nashville radio)
- Social media interactions with country artists (TikTok, Instagram)
- Festival attendance (Stagecoach, CMA Fest, country concerts)
- Backstage connections, fan interactions

**DEGREE 3** (Cultural/lifestyle):
- Lifestyle: hunting, fishing, trucks, rural/southern values, small town, blue collar
- Business: Nashville investments, brand partnerships (Buc-ee's, Carhartt, Yeti)
- Patriotic: military support, veterans, faith, conservative values, freedom themes, first responders

For each connection found, specify:
- type: "artist"|"venue"|"label"|"person"|"brand"|"event"|"media"
- entity: Name of connected entity
- description: How they connect to country music
- degree: 1|2|3 based on directness of connection
- confidence: 0.0-1.0 (only include if >= 0.6)
- evidence: [URLs]

Output raw JSON:
{{"connections":[{{"type":"artist","entity":"Name","description":"Details","degree":1,"confidence":0.85,"evidence":["url"]}}]}}

If none: {{"connections":[]}}

Prefer recent (last 6 months) but include significant historical connections."""

        query = f"""Find ALL "{keyword}" country music connections across all categories in one comprehensive search:

**DIRECT CONNECTIONS (Degree 1):** 
- Is {keyword} a country artist, signed to a country label, on Billboard country charts?
- Performed at Nashville venues: Grand Ole Opry, Ryman, Bluebird Cafe, Lower Broadway bars?
- Collaborations with Morgan Wallen, Luke Combs, Carrie Underwood, Jelly Roll, other country artists?
- CMA Awards, ACM Awards, CMT Awards, Country Rebel features?
- Released country album or single in {current_year}?

**MEDIA & SOCIAL (Degree 2):**
- Bobby Bones Show, CMT/GAC interviews, Nashville radio appearances?
- Viral TikTok/Instagram content with country artists or at country events?
- Festival attendance: Stagecoach, CMA Fest, country concerts, backstage access?
- Country music podcast interviews, Stars & Stripes Sessions?

**CULTURAL & LIFESTYLE (Degree 3):**
- Outdoor lifestyle: hunting, fishing, trucks, rural/small town values?
- Business: Nashville investments, brand deals with country artists, tour sponsorships?
- Patriotic: military/veteran support, faith-based values, conservative alignment?
- Lifestyle brands: Buc-ee's, Carhartt, Yeti associations?

Search comprehensively. Include ALL connection types found with proper degree classification.

Return RAW JSON only:
{{"connections":[{{"type":"person","entity":"Name","description":"Connection","degree":2,"confidence":0.75,"evidence":["url"]}}]}}"""

        try:
            result = await perplexity_service.search_and_analyze(
                query=query,
                system_prompt=system_prompt,
                temperature=0.2,
                deep_research=deep_research
            )
            
            # Parse JSON response
            content = result["content"]
            
            # Remove <think> tags if present (Perplexity reasoning model)
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            
            # Extract JSON from markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 2:
                    content = parts[1].strip()
            
            # Try to find JSON object in the content
            if not content.startswith("{"):
                # Look for first { to last }
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end > start:
                    content = content[start:end]
            
            # Parse JSON
            data = json.loads(content)
            connections = data.get("connections", [])
            
            # Add Perplexity citations if missing
            for conn in connections:
                if not conn.get("evidence") or len(conn.get("evidence", [])) == 0:
                    conn["evidence"] = result.get("citations", [])
            
            logger.info(
                "Comprehensive search complete",
                keyword=keyword,
                connections_found=len(connections),
                model=result.get("model_used"),
                degrees={
                    1: len([c for c in connections if c.get('degree') == 1]),
                    2: len([c for c in connections if c.get('degree') == 2]),
                    3: len([c for c in connections if c.get('degree') == 3])
                }
            )
            
            return connections
            
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON from comprehensive search",
                keyword=keyword,
                error=str(e),
                raw_content=content[:500] if 'content' in locals() else "N/A"
            )
            return []
        except Exception as e:
            logger.error(
                "Comprehensive search failed",
                keyword=keyword,
                error=str(e)
            )
            raise


# Global service instance
connection_analyzer_service = ConnectionAnalyzerService()
