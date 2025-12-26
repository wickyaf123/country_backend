"""Multi-degree connection analyzer for Story Intelligence."""

from typing import List, Dict, Any
import structlog
from json_repair import repair_json

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
    ) -> tuple[List[Dict[str, Any]], str]:
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
            Tuple of (List of connections with degree, type, entity, description, confidence,
            connection chain, and evidence, parsing_status)
            parsing_status can be: "success", "repaired", "partial", "failed"
        """
        logger.info(
            "Finding country music connections (comprehensive single query)", 
            keyword=keyword,
            deep_research_mode=deep_research
        )
        
        try:
            # Execute comprehensive search (now returns tuple)
            all_connections, parsing_status = await self._search_comprehensive_connections(
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
                parsing_status=parsing_status,
                degrees_found={
                    1: len([c for c in all_connections if c['degree'] == 1]),
                    2: len([c for c in all_connections if c['degree'] == 2]),
                    3: len([c for c in all_connections if c['degree'] == 3])
                }
            )
            
            # Return connections with parsing status attached
            return all_connections, parsing_status
            
        except Exception as e:
            logger.error("Connection analysis failed", keyword=keyword, error=str(e))
            return [], "failed"
    
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
    
    def _repair_json(self, content: str) -> str:
        """
        Repair malformed JSON using the json-repair library.
        
        This library handles:
        - Missing quotes around keys/values
        - Trailing commas
        - Unmatched brackets/braces
        - Incomplete trailing objects
        - Common Unicode/escape sequence issues
        - Single quotes instead of double quotes
        - Python-style True/False/None values
        - Comments in JSON
        - And many more edge cases
        
        Args:
            content: The malformed JSON string
        
        Returns:
            Repaired JSON string
        """
        logger.info("Attempting JSON repair with json-repair library", content_length=len(content))
        
        try:
            # Use json-repair library for robust repair
            repaired = repair_json(content)
            logger.info("JSON repair complete", repaired_length=len(repaired))
            return repaired
        except Exception as e:
            logger.error("JSON repair failed", error=str(e))
            # Return original content as fallback
            return content
    
    def _extract_partial_connections(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract individual valid connection objects from malformed JSON.
        
        Attempts to parse individual connection objects even when the overall
        JSON structure is broken. Validates each connection has required fields.
        
        Args:
            content: The malformed JSON string
        
        Returns:
            List of successfully extracted and validated connections
        """
        import json
        import re
        
        logger.info("Attempting partial connection extraction", content_length=len(content))
        
        connections = []
        
        # Strategy 1: Try to find the connections array even in malformed JSON
        # Look for "connections":[...] pattern
        connections_match = re.search(r'"connections"\s*:\s*\[(.*)\]', content, re.DOTALL)
        if connections_match:
            connections_array = connections_match.group(1)
            
            # Try to extract individual objects using regex
            # Match complete object patterns like {"type":"...","entity":"...",...}
            object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            object_matches = re.finditer(object_pattern, connections_array)
            
            for match in object_matches:
                obj_str = match.group(0)
                try:
                    # Try to parse this individual object
                    conn = json.loads(obj_str)
                    
                    # Validate required fields
                    if self._validate_connection(conn):
                        connections.append(conn)
                        logger.debug("Successfully extracted connection", entity=conn.get('entity'))
                    else:
                        logger.debug("Invalid connection object (missing required fields)", obj=obj_str[:100])
                        
                except json.JSONDecodeError:
                    logger.debug("Failed to parse individual connection object", obj=obj_str[:100])
                    continue
        
        # Strategy 2: If no connections array found, try to find individual connection objects anywhere
        if not connections:
            object_pattern = r'\{\s*"type"\s*:\s*"[^"]*"\s*,\s*"entity"\s*:\s*"[^"]*"[^}]*\}'
            object_matches = re.finditer(object_pattern, content)
            
            for match in object_matches:
                obj_str = match.group(0)
                try:
                    conn = json.loads(obj_str)
                    if self._validate_connection(conn):
                        connections.append(conn)
                        logger.debug("Extracted standalone connection", entity=conn.get('entity'))
                except json.JSONDecodeError:
                    continue
        
        logger.info(
            "Partial extraction complete",
            extracted_count=len(connections),
            valid_connections=len([c for c in connections if self._validate_connection(c)])
        )
        
        return connections
    
    def _validate_connection(self, conn: Dict[str, Any]) -> bool:
        """
        Validate that a connection object has all required fields.
        
        Required fields:
        - entity: str
        - description: str
        - degree: int (1, 2, or 3)
        - confidence: float (0.0 - 1.0)
        
        Args:
            conn: Connection dictionary to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(conn, dict):
            return False
        
        # Check required fields exist and have correct types
        if 'entity' not in conn or not isinstance(conn['entity'], str) or not conn['entity'].strip():
            return False
        
        if 'description' not in conn or not isinstance(conn['description'], str) or not conn['description'].strip():
            return False
        
        if 'degree' not in conn or not isinstance(conn['degree'], int) or conn['degree'] not in [1, 2, 3]:
            return False
        
        if 'confidence' not in conn:
            # Set default confidence if missing
            conn['confidence'] = 0.7
        elif not isinstance(conn['confidence'], (int, float)) or not (0.0 <= conn['confidence'] <= 1.0):
            return False
        
        # Type is optional but should be string if present
        if 'type' in conn and not isinstance(conn['type'], str):
            return False
        
        # Evidence is optional but should be list if present
        if 'evidence' in conn and not isinstance(conn['evidence'], list):
            conn['evidence'] = []
        
        return True
    
    async def _search_comprehensive_connections(
        self,
        keyword: str,
        deep_research: bool = False,
        retry_count: int = 0
    ) -> tuple[List[Dict[str, Any]], str]:
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
            retry_count: Number of retry attempts (0 = first attempt)
        
        Returns:
            Tuple of (List of connections across all degrees, parsing_status)
            parsing_status can be: "success", "repaired", "partial", "failed"
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
                parsing_status="success",
                degrees={
                    1: len([c for c in connections if c.get('degree') == 1]),
                    2: len([c for c in connections if c.get('degree') == 2]),
                    3: len([c for c in connections if c.get('degree') == 3])
                }
            )
            
            return connections, "success"
            
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse error",
                keyword=keyword,
                retry_count=retry_count,
                error=str(e),
                error_pos=f"line {e.lineno} col {e.colno}",
                raw_content=content[:500] if 'content' in locals() else "N/A"
            )
            
            # First attempt failed - try repair and retry
            if retry_count == 0:
                logger.info("Attempting JSON repair and retry", keyword=keyword)
                
                try:
                    # Apply repair logic
                    repaired_content = self._repair_json(content)
                    
                    # Try to parse repaired JSON
                    data = json.loads(repaired_content)
                    connections = data.get("connections", [])
                    
                    # Add Perplexity citations if missing
                    for conn in connections:
                        if not conn.get("evidence") or len(conn.get("evidence", [])) == 0:
                            conn["evidence"] = result.get("citations", [])
                    
                    logger.info(
                        "JSON repair successful",
                        keyword=keyword,
                        connections_found=len(connections),
                        parsing_status="repaired"
                    )
                    
                    return connections, "repaired"
                    
                except json.JSONDecodeError as repair_error:
                    logger.warning(
                        "JSON repair failed, attempting partial extraction",
                        keyword=keyword,
                        repair_error=str(repair_error)
                    )
                    
                    # Repair failed - try partial extraction
                    connections = self._extract_partial_connections(content)
                    
                    if connections:
                        logger.info(
                            "Partial extraction successful",
                            keyword=keyword,
                            connections_found=len(connections),
                            parsing_status="partial"
                        )
                        return connections, "partial"
                    else:
                        logger.error(
                            "All parsing attempts failed",
                            keyword=keyword,
                            parsing_status="failed"
                        )
                        return [], "failed"
            
            # Second attempt (retry_count >= 1) - go straight to partial extraction
            else:
                logger.warning(
                    "Retry also failed, attempting partial extraction",
                    keyword=keyword
                )
                
                connections = self._extract_partial_connections(content)
                
                if connections:
                    logger.info(
                        "Partial extraction successful on retry",
                        keyword=keyword,
                        connections_found=len(connections),
                        parsing_status="partial"
                    )
                    return connections, "partial"
                else:
                    logger.error(
                        "All parsing attempts failed on retry",
                        keyword=keyword,
                        parsing_status="failed"
                    )
                    return [], "failed"
                    
        except Exception as e:
            logger.error(
                "Comprehensive search failed",
                keyword=keyword,
                error=str(e)
            )
            raise


# Global service instance
connection_analyzer_service = ConnectionAnalyzerService()
