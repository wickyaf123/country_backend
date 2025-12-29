"""Multi-degree connection analyzer for Story Intelligence."""

from typing import List, Dict, Any
import structlog
from json_repair import repair_json

logger = structlog.get_logger()


class ConnectionAnalyzerService:
    """
    Analyzes 1st, 2nd, and 3rd degree connections from keywords to country music.
    
    Uses Perplexity AI with 3 specialized sequential calls (one per degree) for thorough coverage:
    - Degree 1: The "Official Record" - verified industry connections
    - Degree 2: The "Network Chain" - social graph and proximity
    - Degree 3: The "Cultural Profiler" - lifestyle signals and audience overlap
    """
    
    async def find_country_music_connections(
        self,
        keyword: str,
        deep_research: bool = False
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Find multi-degree connections using 3 specialized sequential searches.
        
        Makes 3 Perplexity AI calls, each optimized for its degree:
        - Degree 1: The "Official Record" - verified credits, charts, performances
        - Degree 2: The "Network Chain" - social graph, bridge people, insider venues
        - Degree 3: The "Cultural Profiler" - brand signals, lifestyle, values alignment
        
        Args:
            keyword: The keyword to analyze
            deep_research: If True, uses sonar-deep-research model (slower, more thorough)
        
        Returns:
            Tuple of (List of connections with degree, type, entity, description, confidence,
            connection chain, and evidence, parsing_status)
            parsing_status can be: "success", "repaired", "partial", "failed"
        """
        logger.info(
            "Finding country music connections (3 sequential degree searches)", 
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
                total_queries=3,  # Now uses 3 sequential calls (one per degree)
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
    
    def _parse_perplexity_response(
        self,
        result: Dict[str, Any],
        keyword: str,
        degree: int
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Parse Perplexity response and extract connections with robust error handling.
        
        Args:
            result: The raw Perplexity API response
            keyword: The keyword being analyzed (for logging)
            degree: The degree being searched (for logging)
        
        Returns:
            Tuple of (connections list, parsing_status)
        """
        import json
        
        content = result.get("content", "")
        
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
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                content = content[start:end]
        
        try:
            # Parse JSON
            data = json.loads(content)
            connections = data.get("connections", [])
            
            # Add Perplexity citations if missing
            for conn in connections:
                if not conn.get("evidence") or len(conn.get("evidence", [])) == 0:
                    conn["evidence"] = result.get("citations", [])
            
            return connections, "success"
            
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON parse error",
                keyword=keyword,
                degree=degree,
                error=str(e),
                raw_content=content[:500] if content else "N/A"
            )
            
            # Try repair
            try:
                repaired_content = self._repair_json(content)
                data = json.loads(repaired_content)
                connections = data.get("connections", [])
                
                for conn in connections:
                    if not conn.get("evidence") or len(conn.get("evidence", [])) == 0:
                        conn["evidence"] = result.get("citations", [])
                
                logger.info("JSON repair successful", keyword=keyword, degree=degree)
                return connections, "repaired"
                
            except json.JSONDecodeError:
                # Try partial extraction
                connections = self._extract_partial_connections(content)
                
                if connections:
                    logger.info("Partial extraction successful", keyword=keyword, degree=degree)
                    return connections, "partial"
                else:
                    logger.error("All parsing attempts failed", keyword=keyword, degree=degree)
                    return [], "failed"
                    
    async def _search_comprehensive_connections(
        self,
        keyword: str,
        deep_research: bool = False,
        retry_count: int = 0
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Three-call approach: One specialized search per degree for thorough coverage.
        
        Makes 3 sequential Perplexity calls:
        - Degree 1: Direct artist/venue/label connections (The "Business")
        - Degree 2: Network/Social connections (The "Hang" & Social Graph)
        - Degree 3: Cultural/Lifestyle signals (The "Vibe" & Audience)
        
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
        
        current_year = datetime.now().year
        
        all_connections = []
        parsing_statuses = []
        
        # ===== DEGREE 1: THE OFFICIAL RECORD (The "Business") =====
        system_prompt_d1 = f"""You are a Music Industry Archivist specializing in verified, official country music records.

RETURN ONLY RAW JSON. No markdown, no code blocks, no <think> tags.

YOUR MISSION: Find strict, verifiable proof of professional participation in the Country Music industry.

WHAT TO SEARCH:
- **Credits**: ASCAP/BMI/SESAC songwriting credits, production credits, background vocal credits on country tracks.
- **Charts**: Billboard Country charts, iTunes Country charts, Spotify Viral Country playlists.
- **Official Stages**: Grand Ole Opry, Ryman Auditorium, CMA Fest Main Stage, ACM Awards, CMT Awards.
- **Business**: Signed to Nashville-based label, official management by Nashville agencies.
- **Family**: Immediate family members (parent, sibling, child) who are country artists.

EXCLUSION RULE: Ignore social media rumors or unverified gossip. If there is no official record, return nothing.

For each connection:
- type: "credits" | "charts" | "performance" | "business" | "family"
- entity: Name of Artist, Label, Venue, or Song.
- description: Specific details with dates. "Co-wrote 'Song Title' with [Artist] in 2023."
- degree: 1
- confidence: 0.9-1.0 (only high confidence for verified records)
- evidence: [URLs to official sources]

Output JSON:
{{"connections":[...]}}
If none: {{"connections":[]}}
"""

        query_d1 = f"""Find ALL verified DIRECT country music connections for "{keyword}".

SEARCH:
- "{keyword} songwriting credits country music"
- "{keyword} ASCAP BMI SESAC country"
- "{keyword} Billboard country chart"
- "{keyword} Grand Ole Opry performance"
- "{keyword} Ryman Auditorium"
- "{keyword} CMA Awards ACM Awards CMT Awards"
- "{keyword} signed Nashville record label"
- "{keyword} country album single release {current_year}"
- "{keyword} collaboration Morgan Wallen Luke Combs Jelly Roll"

Return RAW JSON only:
{{"connections":[{{"type":"credits","entity":"Song/Artist","description":"...","degree":1,"confidence":0.95,"evidence":["..."]}}]}}"""

        # ===== DEGREE 2: THE NETWORK CHAIN (The "Hang" & Social Graph) =====
        system_prompt_d2 = f"""You are a Social Network Investigator and Nashville Insider.

RETURN ONLY RAW JSON. No markdown, no code blocks, no <think> tags.

YOUR MISSION: Uncover the SOCIAL GRAPH and PROXIMITY connections. Find the "bridge people" and "the hang."

WHAT TO SEARCH:

**The "Bridge Person" (Triangulation):**
- Trace through spouses, exes, best friends, dating history.
- Example: Subject dates Person X → Person X is best friends with Morgan Wallen.
- Look for connections to wives/partners of stars: Bunnie Xo, Brittany Aldean, KT Smith, Nicole Hocking.

**The Podcast Circuit (Gateway Media):**
- Appearances on: Bobby Bones Show, Bussin' With The Boys, Theo Von, Whiskey Riff, God's Country, Barstool Sports.

**The "Dive Bar" Locator (Where Deals Happen):**
- Spotted at: Losers Bar & Grill, Winners, The Listening Room, Red Door Saloon, Soho House Nashville, The Graduate Nashville.

**Shared Teams:**
- Same Nashville agent, manager, publicist, personal trainer, or stylist as country stars.

**Viral Crossovers:**
- TikTok duets/stitches with country artists.
- Instagram stories featuring country stars at private events.

For each connection:
- type: "bridge_person" | "podcast" | "venue_sighting" | "shared_team" | "viral_crossover"
- entity: Name of Person, Podcast, or Venue.
- description: TELL THE STORY. "Photographed at [Venue] with [Person], who is married to [Country Star]."
- degree: 2
- confidence: 0.7-0.9
- evidence: [URLs]

Output JSON:
{{"connections":[...]}}
If none: {{"connections":[]}}
"""

        query_d2 = f"""Find ALL social and network connections for "{keyword}" to Country Music. Trace the social graph.

SEARCH:
- "{keyword} dating country singer"
- "{keyword} ex-girlfriend ex-boyfriend country star"
- "{keyword} best friend Nashville"
- "{keyword} party with Morgan Wallen Luke Combs"
- "{keyword} Bunnie Xo Brittany Aldean KT Smith" (spouse connections)
- "{keyword} manager agent Nashville"
- "{keyword} spotted Losers Bar Nashville"
- "{keyword} Winners Bar Nashville"
- "{keyword} Soho House Nashville"
- "{keyword} Bobby Bones Show interview"
- "{keyword} Bussin With The Boys podcast"
- "{keyword} Theo Von podcast country"
- "{keyword} Whiskey Riff feature"
- "{keyword} TikTok duet country song"
- "{keyword} Instagram story country artist"

Return RAW JSON only:
{{"connections":[{{"type":"bridge_person","entity":"Person X","description":"Dated Person X, who is the sister of Country Star Y.","degree":2,"confidence":0.85,"evidence":["..."]}}]}}"""

        # ===== DEGREE 3: THE CULTURAL PROFILER (The "Vibe" & Lifestyle) =====
        system_prompt_d3 = f"""You are a Sociologist and Lifestyle Marketer specializing in cultural signals.

RETURN ONLY RAW JSON. No markdown, no code blocks, no <think> tags.

YOUR MISSION: Identify CODED LIFESTYLE SIGNALS that align the subject with the Country Music audience. Look for brand deals, activities, values, and audience overlap.

WHAT TO SEARCH:

**The "Uniform" (Brand Signals):**
- Sponsorship OR heavy organic use of: Carhartt, Yeti, Sitka, Mossy Oak, Tecovas, Seager, Kimes Ranch, King Ranch, Bass Pro Shops, Cabela's, Ariat, Wrangler, Boot Barn.
- NOT just "wearing boots once." Look for partnerships or consistent public usage.

**The "Activity" Profile (The Three Pillars):**
- Motorsports: NASCAR, Monster Jam, Dirt Track Racing, off-roading.
- Outdoors: Deep-sea fishing, Elk/Duck/Deer hunting, PBR Rodeo, NFR (National Finals Rodeo).
- Rural Living: Farming, homesteading, owning land in "country wealth" zones (Leiper's Fork, Franklin TN, Bitterroot Valley MT, Jackson Hole WY).

**The "Values" Alignment:**
- Public support for Military/Veterans (Folds of Honor, USO).
- First Responder advocacy.
- Blue Collar/Working Class pride.
- Faith-based initiatives.

**Audience Mirror (Psychographic Overlap):**
- "Yellowstone" fandom, UFC attendance, Barstool Sports universe.
- Joe Rogan/Theo Von crossover (if discussing lifestyle, not just appearing).

INFERENCE RULE: If the subject has zero music connections but checks 3+ boxes here, they are a HIGH-CONFIDENCE Degree 3 match.

For each connection:
- type: "brand_signal" | "outdoor_lifestyle" | "motorsports" | "values_alignment" | "audience_overlap" | "geographic"
- entity: Name of Brand, Activity, Cause, or Location.
- description: Specific context. "Official Yeti ambassador since 2022" or "Owns 500-acre ranch in Franklin, TN."
- degree: 3
- confidence: 0.6-0.85
- evidence: [URLs]

Output JSON:
{{"connections":[...]}}
If none: {{"connections":[]}}
"""

        query_d3 = f"""Find ALL cultural and lifestyle connections for "{keyword}" to the Country Music audience.

SEARCH:
- "{keyword} Carhartt sponsor", "{keyword} Yeti ambassador"
- "{keyword} Tecovas cowboy boots", "{keyword} Seager clothing"
- "{keyword} Bass Pro Shops", "{keyword} Cabela's"
- "{keyword} hunting fishing brand deal"
- "{keyword} NASCAR race attendance", "{keyword} Monster Jam"
- "{keyword} duck hunting", "{keyword} elk hunting", "{keyword} deer hunting"
- "{keyword} PBR rodeo", "{keyword} NFR National Finals Rodeo"
- "{keyword} ranch property", "{keyword} farm land"
- "{keyword} house Franklin Tennessee", "{keyword} property Leiper's Fork"
- "{keyword} ranch Montana Wyoming Texas"
- "{keyword} military veterans charity", "{keyword} Folds of Honor", "{keyword} USO"
- "{keyword} first responders support", "{keyword} blue collar"
- "{keyword} Yellowstone fan", "{keyword} Kevin Costner"
- "{keyword} UFC fight attendance"
- "{keyword} Barstool Sports"

Return RAW JSON only:
{{"connections":[{{"type":"brand_signal","entity":"Yeti","description":"Official Yeti ambassador, featured in their 2024 campaign.","degree":3,"confidence":0.8,"evidence":["..."]}}]}}"""

        # ===== EXECUTE 3 SEQUENTIAL CALLS =====
        degree_configs = [
            {"degree": 1, "system_prompt": system_prompt_d1, "query": query_d1, "temperature": 0.1},
            {"degree": 2, "system_prompt": system_prompt_d2, "query": query_d2, "temperature": 0.3},
            {"degree": 3, "system_prompt": system_prompt_d3, "query": query_d3, "temperature": 0.3},
        ]
        
        for config in degree_configs:
            degree = config["degree"]
            logger.info(
                f"Searching Degree {degree} connections",
                keyword=keyword,
                degree=degree
            )
            
            try:
                result = await perplexity_service.search_and_analyze(
                    query=config["query"],
                    system_prompt=config["system_prompt"],
                    temperature=config["temperature"],
                    deep_research=deep_research
                )
                
                connections, status = self._parse_perplexity_response(result, keyword, degree)
                
                # Ensure all connections have the correct degree
                for conn in connections:
                    conn["degree"] = degree
                
                all_connections.extend(connections)
                parsing_statuses.append(status)
                
                logger.info(
                    f"Degree {degree} search complete",
                    keyword=keyword,
                    connections_found=len(connections),
                    parsing_status=status
                )
                
            except Exception as e:
                logger.error(
                    f"Degree {degree} search failed",
                    keyword=keyword,
                    error=str(e)
                )
                parsing_statuses.append("failed")
        
        # Determine overall parsing status
        if all(s == "success" for s in parsing_statuses):
            overall_status = "success"
        elif all(s == "failed" for s in parsing_statuses):
            overall_status = "failed"
        elif "success" in parsing_statuses or "repaired" in parsing_statuses:
            overall_status = "partial"
        else:
            overall_status = "partial"
        
        logger.info(
            "All degree searches complete",
            keyword=keyword,
            total_connections=len(all_connections),
            overall_status=overall_status,
            degrees={
                1: len([c for c in all_connections if c.get('degree') == 1]),
                2: len([c for c in all_connections if c.get('degree') == 2]),
                3: len([c for c in all_connections if c.get('degree') == 3])
            }
        )
        
        return all_connections, overall_status


# Global service instance
connection_analyzer_service = ConnectionAnalyzerService()
