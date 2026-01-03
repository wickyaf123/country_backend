"""Tier-based relevance classifier for Story Intelligence."""

from typing import List, Dict, Any
import structlog
from json_repair import repair_json

logger = structlog.get_logger()


class ConnectionAnalyzerService:
    """
    Classifies keywords into 3 tiers based on country MUSIC relevance.
    
    Tier 1 (0.9-1.0): Direct country music stories
    Tier 2 (0.5-0.8): Related topics with real connections
    Tier 3 (0.0-0.4): Unrelated topics
    """
    
    async def find_country_music_connections(
        self,
        keyword: str,
        deep_research: bool = False
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Classify keyword relevance and return connection data.
        
        This is the main entry point that maintains backward compatibility
        but now uses tier-based classification instead of degree-based.
        
        Args:
            keyword: The keyword to analyze
            deep_research: If True, uses more thorough analysis (currently unused)
        
        Returns:
            Tuple of (List of connections, parsing_status)
        """
        logger.info("Classifying keyword relevance", keyword=keyword)
        
        try:
            # Perform tier classification
            classification = await self.classify_keyword_relevance(keyword)
            
            # Convert to connection format for backward compatibility
            connections = []
            if classification['is_relevant']:
                connection = {
                    'tier': classification['tier'],
                    'type': 'classification',
                    'entity': classification.get('entity') or keyword,
                    'description': classification['classification_reason'],
                    'confidence': classification['relevance_score'],
                    'evidence': [],
                    'connection_chain': self._format_connection_chain(keyword, classification)
                }
                connections.append(connection)
            
            logger.info(
                "Classification complete",
                keyword=keyword,
                tier=classification['tier'],
                relevance_score=classification['relevance_score'],
                is_relevant=classification['is_relevant']
            )
            
            return connections, "success"
            
        except Exception as e:
            logger.error("Classification failed", keyword=keyword, error=str(e))
            return [], "failed"
    
    async def classify_keyword_relevance(
        self,
        keyword: str
    ) -> Dict[str, Any]:
        """
        Classify keyword into 3 tiers based on country MUSIC relevance.
        
        Returns: {
            tier: 1|2|3,
            relevance_score: 0.0-1.0,
            is_relevant: true/false,
            classification_reason: str,
            country_music_connection: str|null,
            entity: str|null
        }
        """
        from services.perplexity_service import perplexity_service
        
        system_prompt = """You are a Country Music News Editor for Country Rebel.

RETURN ONLY RAW JSON. No markdown, no code blocks, no <think> tags.

CRITICAL: Classify how relevant this topic is to COUNTRY MUSIC (the music genre), NOT "country lifestyle" or "rural America."

🎵 COUNTRY MUSIC means: country music artists, songs, albums, tours, awards shows (CMA, ACM, CMT), Nashville music industry, country music festivals, country radio.

TIER 1 - DIRECT COUNTRY MUSIC STORY (relevance: 0.9-1.0):
The topic IS about country music. Examples:
- Chris Stapleton announces new tour ✓
- Morgan Wallen releases album ✓
- CMA Awards winners announced ✓
- New country artist goes viral on TikTok ✓
- Nashville Music Row news ✓

TIER 2 - RELATED TOPIC (relevance: 0.5-0.8):
NOT about country music, but has a REAL, DOCUMENTED connection. Examples:
- Glen Powell (Twister movie features country soundtrack) ✓
- Yellowstone TV show (prominently features country music) ✓
- Super Bowl halftime (if country artist performing) ✓
- A pop star who has done country duets ✓

TIER 3 - UNRELATED (relevance: 0.0-0.4):
No meaningful connection to country MUSIC. Examples:
- Nikki Minaj news ✗
- Random political news ✗
- NBA playoffs ✗
- General celebrity gossip with no music tie ✗

⚠️ DO NOT force connections:
- Owning a ranch ≠ country music relevance
- Wearing cowboy boots ≠ country music relevance
- Dating someone from Nashville ≠ country music relevance
- Liking hunting/fishing ≠ country music relevance

ONLY classify as Tier 1 or 2 if there's a REAL connection to the MUSIC GENRE.

Output JSON format:
{
  "tier": 1|2|3,
  "relevance_score": 0.0-1.0,
  "is_relevant": true|false,
  "classification_reason": "Brief explanation of why this tier was assigned",
  "country_music_connection": "Specific connection to country MUSIC if any, or null",
  "entity": "Country artist/song/event involved, or null"
}

If tier 3, return:
{
  "tier": 3,
  "relevance_score": 0.0,
  "is_relevant": false,
  "classification_reason": "No connection to country music",
  "country_music_connection": null,
  "entity": null
}"""

        query = f"""Classify this trending topic for Country Music relevance:

TOPIC: "{keyword}"

Is this topic:
1. DIRECTLY about country music (artist, song, tour, awards)?
2. RELATED but not directly country (movie/TV with country soundtrack, crossover artist)?
3. UNRELATED to country music?

Be HONEST. If there's no real connection to COUNTRY MUSIC (the genre), classify as Tier 3.
Do NOT force-fit lifestyle/culture connections. We only care about THE MUSIC.

Return only JSON classification."""

        try:
            result = await perplexity_service.search_and_analyze(
                query=query,
                system_prompt=system_prompt,
                temperature=0.1
            )
            
            # Parse response
            content = result.get("content", "")
            
            # Remove <think> tags if present
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
            
            # Parse JSON
            import json
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try repair
                logger.warning("JSON parse failed, attempting repair", keyword=keyword)
                repaired_content = self._repair_json(content)
                data = json.loads(repaired_content)
            
            # Validate and normalize response
            tier = data.get('tier', 3)
            if tier not in [1, 2, 3]:
                tier = 3
            
            relevance_score = data.get('relevance_score', 0.0)
            if not isinstance(relevance_score, (int, float)) or not (0.0 <= relevance_score <= 1.0):
                relevance_score = 0.0
            
            is_relevant = tier <= 2 and relevance_score >= 0.5
            
            classification = {
                'tier': tier,
                'relevance_score': relevance_score,
                'is_relevant': is_relevant,
                'classification_reason': data.get('classification_reason', 'No classification reason provided'),
                'country_music_connection': data.get('country_music_connection'),
                'entity': data.get('entity')
            }
            
            logger.info(
                "Classification successful",
                keyword=keyword,
                tier=tier,
                score=relevance_score,
                is_relevant=is_relevant
            )
            
            return classification
            
        except Exception as e:
            logger.error("Classification failed", keyword=keyword, error=str(e))
            # Return Tier 3 (unrelated) as safe default
            return {
                'tier': 3,
                'relevance_score': 0.0,
                'is_relevant': False,
                'classification_reason': f'Classification error: {str(e)}',
                'country_music_connection': None,
                'entity': None
            }
    
    def _format_connection_chain(self, keyword: str, classification: Dict) -> str:
        """
        Format connection chain for visualization.
        """
        tier = classification.get('tier', 3)
        entity = classification.get('entity') or keyword
        
        if tier == 1:
            return f"{keyword} → Direct Country Music"
        elif tier == 2:
            return f"{keyword} → {entity} → Country Music"
        else:
            return f"{keyword} → No Connection"
    
    def _repair_json(self, content: str) -> str:
        """
        Repair malformed JSON using the json-repair library.
        """
        logger.info("Attempting JSON repair", content_length=len(content))
        
        try:
            repaired = repair_json(content)
            logger.info("JSON repair complete", repaired_length=len(repaired))
            return repaired
        except Exception as e:
            logger.error("JSON repair failed", error=str(e))
            return content


# Global service instance
connection_analyzer_service = ConnectionAnalyzerService()
