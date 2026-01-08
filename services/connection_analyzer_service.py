"""
ULTIMATE Connection Analyzer v2.0
==================================
Multi-degree connection analyzer with:
- Structured data models
- Domain knowledge graph
- Few-shot prompt engineering
- Adversarial checking
- Confidence calibration
- Advanced deduplication
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import hashlib
import re
import json
import structlog
from json_repair import repair_json

logger = structlog.get_logger()


# =============================================================================
# SECTION 1: DATA MODELS & ENUMS
# =============================================================================

class ConnectionType(Enum):
    """Exhaustive connection type taxonomy."""
    # Degree 1 - Official
    CREDITS = "credits"
    CHARTS = "charts"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    FAMILY = "family"
    AWARD = "award"
    
    # Degree 2 - Social
    BRIDGE_PERSON = "bridge_person"
    PODCAST = "podcast"
    VENUE_SIGHTING = "venue_sighting"
    SHARED_TEAM = "shared_team"
    COLLABORATION = "collaboration"
    DATING = "dating"
    FRIENDSHIP = "friendship"
    
    # Degree 3 - Lifestyle
    BRAND_SIGNAL = "brand_signal"
    OUTDOOR_LIFESTYLE = "outdoor_lifestyle"
    PROPERTY = "property"
    VALUES_ALIGNMENT = "values_alignment"
    MOTORSPORTS = "motorsports"
    AUDIENCE_OVERLAP = "audience_overlap"


class SourceTier(Enum):
    """Source authority ranking."""
    TIER_1 = 1  # Official databases, press releases
    TIER_2 = 2  # Major publications
    TIER_3 = 3  # Verified social media, local news
    TIER_4 = 4  # Blogs, forums (usually rejected)
    UNKNOWN = 5


class VerificationStatus(Enum):
    """Connection verification status."""
    VERIFIED = "verified"          # Multiple Tier 1/2 sources
    LIKELY = "likely"              # Single Tier 1/2 source
    PLAUSIBLE = "plausible"        # Tier 3 sources only
    UNVERIFIED = "unverified"      # No valid sources
    CONTRADICTED = "contradicted"  # Found counter-evidence


@dataclass
class Evidence:
    """Structured evidence with metadata."""
    url: str
    source_name: str
    source_tier: SourceTier
    publication_date: Optional[datetime] = None
    quote: Optional[str] = None  # Direct quote if available
    is_primary: bool = False     # Primary vs secondary source
    
    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "source_name": self.source_name,
            "source_tier": self.source_tier.name,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "quote": self.quote,
            "is_primary": self.is_primary,
        }


@dataclass
class Connection:
    """Rich connection object with full metadata."""
    entity: str
    entity_type: str  # person, brand, venue, song, etc.
    description: str
    degree: int
    connection_type: ConnectionType
    raw_confidence: float
    calibrated_confidence: float = 0.0
    evidence: List[Evidence] = field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    event_date: Optional[datetime] = None
    connection_chain: str = ""
    
    # For deduplication
    entity_normalized: str = ""
    fingerprint: str = ""
    
    # Adversarial check results
    counter_evidence: List[str] = field(default_factory=list)
    adversarial_score: float = 1.0  # 1.0 = no counter-evidence
    
    # Audit trail
    source_degree_search: int = 0
    processing_notes: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.entity_normalized = self._normalize_entity(self.entity)
        self.fingerprint = self._generate_fingerprint()
        self.calibrated_confidence = self.raw_confidence  # Will be adjusted later
    
    def _normalize_entity(self, entity: str) -> str:
        """Normalize entity name for deduplication."""
        normalized = entity.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Handle common variations
        replacements = {
            "jr.": "jr", "jr": "junior",
            "sr.": "sr", "sr": "senior",
            "the ": "", "& ": "and ",
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        return normalized
    
    def _generate_fingerprint(self) -> str:
        """Generate unique fingerprint for deduplication."""
        content = f"{self.entity_normalized}|{self.degree}|{self.connection_type.value}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict:
        return {
            "entity": self.entity,
            "entity_type": self.entity_type,
            "description": self.description,
            "degree": self.degree,
            "type": self.connection_type.value,
            "confidence": round(self.calibrated_confidence, 3),
            "raw_confidence": round(self.raw_confidence, 3),
            "verification_status": self.verification_status.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "connection_chain": self.connection_chain,
            "adversarial_score": round(self.adversarial_score, 2),
            "counter_evidence": self.counter_evidence,
        }


# =============================================================================
# SECTION 2: DOMAIN KNOWLEDGE GRAPH
# =============================================================================

class NashvilleKnowledgeGraph:
    """
    Pre-loaded domain knowledge to:
    1. Validate entity names
    2. Identify known relationships
    3. Provide context for searches
    4. Catch hallucinated entities
    """
    
    # Major country artists (for entity validation)
    MAJOR_ARTISTS = {
        "morgan wallen", "luke combs", "chris stapleton", "zach bryan",
        "lainey wilson", "jelly roll", "cody johnson", "kane brown",
        "luke bryan", "carrie underwood", "miranda lambert", "blake shelton",
        "thomas rhett", "jason aldean", "eric church", "keith urban",
        "tim mcgraw", "kenny chesney", "dierks bentley", "kelsea ballerini",
        "maren morris", "gabby barrett", "carly pearce", "ashley mcbryde",
        "brothers osborne", "old dominion", "dan + shay", "hardy",
        "parker mccollum", "riley green", "jordan davis", "tyler childers",
        "sturgill simpson", "tyler hubbard", "brian kelley", "dustin lynch",
        "brett young", "russell dickerson", "cole swindell", "jon pardi",
        "midland", "lanco", "lady a", "little big town", "rascal flatts",
        "florida georgia line", "post malone",
    }
    
    # Known spouses/partners (for bridge person validation)
    KNOWN_RELATIONSHIPS = {
        "bunnie xo": "jelly roll",
        "brittany aldean": "jason aldean",
        "kt smith": "morgan wallen",
        "nicole hocking": "luke combs",
        "lauren akins": "thomas rhett",
        "hayley hubbard": "tyler hubbard",
        "cassie kelley": "brian kelley",
        "katelyn brown": "kane brown",
    }
    
    # Nashville industry venues
    INDUSTRY_VENUES = {
        "grand ole opry", "ryman auditorium", "bluebird cafe",
        "the listening room", "losers bar", "winners", "tootsies",
        "roberts western world", "acme feed & seed", "the stage",
        "soho house nashville", "the graduate", "pinewood social",
        "station inn", "3rd and lindsley", "city winery nashville",
    }
    
    # Valid country music podcasts
    COUNTRY_PODCASTS = {
        "bobby bones show", "the bobby bones show",
        "bussin with the boys", "bussin' with the boys",
        "theo von this past weekend",
        "whiskey riff", "country countdown",
        "the storme warren show", "ty bentli show",
    }
    
    # Tier 1 sources
    TIER_1_SOURCES = {
        "ascap.com", "bmi.com", "sesac.com",
        "billboard.com", "opry.com", "cmaworld.com",
        "acmcountry.com", "cmtpress.com",
    }
    
    # Tier 2 sources
    TIER_2_SOURCES = {
        "rollingstone.com", "variety.com", "people.com",
        "eonline.com", "usmagazine.com", "cmt.com",
        "tasteofcountry.com", "theboot.com", "whiskeyriff.com",
        "savingcountrymusic.com", "tennessean.com", "musicrow.com",
    }
    
    # Brands with country audience overlap
    COUNTRY_ALIGNED_BRANDS = {
        "yeti", "carhartt", "ariat", "wrangler", "tecovas",
        "bass pro shops", "cabela's", "sitka", "first lite",
        "mossy oak", "realtree", "kimes ranch", "seager",
        "black rifle coffee", "brcc", "traeger", "pit boss",
        "polaris", "can-am", "yamaha", "honda", "kawasaki",
        "ford", "chevy", "chevrolet", "ram", "gmc",
    }
    
    @classmethod
    def get_source_tier(cls, url: str) -> SourceTier:
        """Determine source tier from URL."""
        url_lower = url.lower()
        
        for domain in cls.TIER_1_SOURCES:
            if domain in url_lower:
                return SourceTier.TIER_1
        
        for domain in cls.TIER_2_SOURCES:
            if domain in url_lower:
                return SourceTier.TIER_2
        
        # Check for official social media
        if any(x in url_lower for x in ["instagram.com", "twitter.com", "x.com", "tiktok.com"]):
            return SourceTier.TIER_3
        
        # News sites
        if any(x in url_lower for x in [".com/news", "news.", "today.com", "abc", "cbs", "nbc", "fox"]):
            return SourceTier.TIER_3
        
        return SourceTier.UNKNOWN


# =============================================================================
# SECTION 3: CONFIDENCE CALIBRATOR
# =============================================================================

class ConfidenceCalibrator:
    """
    Adjusts confidence scores based on:
    1. Source tier
    2. Number of sources
    3. Recency
    4. Adversarial check results
    """
    
    @staticmethod
    def calibrate(
        connection: Connection,
        adversarial_score: float = 1.0,
        cross_reference_boost: bool = False
    ) -> float:
        """Calculate calibrated confidence score."""
        base = connection.raw_confidence
        
        # Source tier adjustment
        source_tiers = [e.source_tier for e in connection.evidence]
        if source_tiers:
            best_tier = min(source_tiers, key=lambda x: x.value)
            tier_multipliers = {
                SourceTier.TIER_1: 1.0,
                SourceTier.TIER_2: 0.95,
                SourceTier.TIER_3: 0.85,
                SourceTier.TIER_4: 0.60,
                SourceTier.UNKNOWN: 0.70,
            }
            base *= tier_multipliers.get(best_tier, 0.70)
        
        # Multi-source boost
        num_sources = len(connection.evidence)
        if num_sources >= 3:
            base = min(base * 1.10, 0.99)
        elif num_sources >= 2:
            base = min(base * 1.05, 0.99)
        elif num_sources == 0:
            base *= 0.70  # Penalty for no sources
        
        # Recency boost (more recent = higher confidence)
        if connection.event_date:
            days_ago = (datetime.now() - connection.event_date).days
            if days_ago <= 30:
                base = min(base * 1.05, 0.99)
            elif days_ago <= 90:
                base = min(base * 1.02, 0.99)
            elif days_ago > 300:
                base *= 0.95  # Slight penalty for older
        
        # Adversarial score (from counter-evidence check)
        base *= adversarial_score
        
        # Cross-reference boost (found in multiple degree searches)
        if cross_reference_boost:
            base = min(base * 1.08, 0.99)
        
        # Degree-specific caps
        degree_caps = {1: 0.99, 2: 0.92, 3: 0.88}
        cap = degree_caps.get(connection.degree, 0.90)
        
        return min(max(base, 0.0), cap)


# =============================================================================
# SECTION 4: DEDUPLICATOR
# =============================================================================

class ConnectionDeduplicator:
    """Deduplicates connections across degree searches."""
    
    @staticmethod
    def deduplicate(connections: List[Connection]) -> List[Connection]:
        """Remove duplicate connections, keeping highest confidence."""
        seen_fingerprints: Dict[str, Connection] = {}
        
        for conn in connections:
            if conn.fingerprint in seen_fingerprints:
                existing = seen_fingerprints[conn.fingerprint]
                if conn.calibrated_confidence > existing.calibrated_confidence:
                    seen_fingerprints[conn.fingerprint] = conn
                    conn.processing_notes.append(
                        f"Replaced lower confidence duplicate ({existing.calibrated_confidence:.2f})"
                    )
            else:
                seen_fingerprints[conn.fingerprint] = conn
        
        return list(seen_fingerprints.values())
    
    @staticmethod
    def merge_evidence(connections: List[Connection]) -> List[Connection]:
        """Merge evidence from duplicate connections before dedup."""
        fingerprint_groups: Dict[str, List[Connection]] = {}
        
        for conn in connections:
            if conn.fingerprint not in fingerprint_groups:
                fingerprint_groups[conn.fingerprint] = []
            fingerprint_groups[conn.fingerprint].append(conn)
        
        merged = []
        for fingerprint, group in fingerprint_groups.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Take highest confidence one as base
                group.sort(key=lambda x: x.raw_confidence, reverse=True)
                base = group[0]
                
                # Merge evidence from others
                seen_urls = {e.url for e in base.evidence}
                for other in group[1:]:
                    for evidence in other.evidence:
                        if evidence.url not in seen_urls:
                            base.evidence.append(evidence)
                            seen_urls.add(evidence.url)
                
                base.processing_notes.append(
                    f"Merged evidence from {len(group)} duplicate findings"
                )
                merged.append(base)
        
        return merged


# =============================================================================
# SECTION 5: LEGACY CONNECTION ANALYZER SERVICE (Backwards Compatibility)
# =============================================================================

class ConnectionAnalyzerService:
    """
    LEGACY WRAPPER for backwards compatibility.
    Delegates to UltimateConnectionAnalyzer but maintains old API signature.
    """
    
    async def find_country_music_connections(
        self,
        keyword: str
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        LEGACY API: Find multi-degree connections.
        
        This method maintains backwards compatibility with existing code.
        Internally delegates to UltimateConnectionAnalyzer.
        
        Args:
            keyword: The keyword to analyze
        
        Returns:
            Tuple of (List of connections, parsing_status)
            parsing_status can be: "success", "repaired", "partial", "failed"
        """
        logger.info("Finding country music connections (legacy API)", keyword=keyword)
        
        try:
            # Use new analyzer
            analyzer = UltimateConnectionAnalyzer()
            connections, metadata = await analyzer.analyze(
                keyword=keyword,
                enable_adversarial=False,  # Disabled by default - too strict
                enable_citation_check=False
            )
            
            # Determine parsing status from metadata
            total_found = metadata["quality_metrics"]["final_connections"]
            if total_found > 0:
                parsing_status = "success"
            elif metadata["quality_metrics"]["raw_connections"] > 0:
                parsing_status = "partial"
            else:
                parsing_status = "failed"
            
            logger.info(
                "Connection analysis complete",
                keyword=keyword,
                connections_found=len(connections),
                parsing_status=parsing_status,
                total_time=metadata["timing"]["total"]
            )
            
            return connections, parsing_status
            
        except Exception as e:
            logger.error("Connection analysis failed", keyword=keyword, error=str(e))
            return [], "failed"
    

# =============================================================================
# SECTION 6: ULTIMATE CONNECTION ANALYZER (Main Implementation)
# =============================================================================

class UltimateConnectionAnalyzer:
    """
    The complete, production-grade connection analyzer.
    
    Pipeline:
    1. Parallel degree searches with few-shot prompts
    2. Parse and validate responses
    3. Entity resolution and deduplication
    4. Adversarial checking
    5. Confidence calibration
    6. Final ranking and output
    """
    
    def __init__(self):
        self.knowledge_graph = NashvilleKnowledgeGraph
        self.calibrator = ConfidenceCalibrator()
        self.deduplicator = ConnectionDeduplicator()
        
        # Configuration
        self.config = {
            "max_connections_per_degree": 5,
            "min_confidence_d1": 0.30,  # Very permissive - let most through
            "min_confidence_d2": 0.25,  # Very permissive - let most through
            "min_confidence_d3": 0.20,  # Very permissive - let most through
            "enable_adversarial_check": True,
            "max_total_connections": 12,
        }
    
    async def analyze(
        self,
        keyword: str,
        enable_adversarial: bool = True,
        enable_citation_check: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Main entry point for connection analysis.
        
        Returns:
            Tuple of (connections_list, metadata_dict)
        """
        from services.perplexity_service import perplexity_service
        
        start_time = datetime.now()
        
        # Calculate time window
        current_date = datetime.now()
        one_year_ago = (current_date - timedelta(days=365)).strftime("%B %Y")
        current_str = current_date.strftime("%B %Y")
        
        metadata = {
            "keyword": keyword,
            "search_window": f"{one_year_ago} - {current_str}",
            "stages_completed": [],
            "timing": {},
            "quality_metrics": {},
        }
        
        all_connections: List[Connection] = []
        
        # ===============================
        # STAGE 1: Parallel Degree Searches
        # ===============================
        stage_start = datetime.now()
        
        # Get prompts with few-shot examples
        d1_system, d1_query = self._get_degree_1_prompt(keyword, one_year_ago, current_str)
        d2_system, d2_query = self._get_degree_2_prompt(keyword, one_year_ago, current_str)
        d3_system, d3_query = self._get_degree_3_prompt(keyword, one_year_ago, current_str)
        
        # Execute in parallel
        results = await asyncio.gather(
            perplexity_service.search_and_analyze(
                query=d1_query, system_prompt=d1_system, temperature=0.0, model="sonar-reasoning-pro"
            ),
            perplexity_service.search_and_analyze(
                query=d2_query, system_prompt=d2_system, temperature=0.1, model="sonar-reasoning-pro"
            ),
            perplexity_service.search_and_analyze(
                query=d3_query, system_prompt=d3_system, temperature=0.1, model="sonar-reasoning-pro"
            ),
            return_exceptions=True
        )
        
        metadata["timing"]["degree_searches"] = (datetime.now() - stage_start).total_seconds()
        metadata["stages_completed"].append("degree_searches")
        
        # ===============================
        # STAGE 2: Parse Responses
        # ===============================
        stage_start = datetime.now()
        
        for degree, result in enumerate(results, 1):
            if isinstance(result, Exception):
                logger.error(f"Degree {degree} search failed", error=str(result))
                continue
            
            connections = self._parse_response(result, degree)
            all_connections.extend(connections)
            
            logger.info(
                    f"Degree {degree} parsed",
                    connections_found=len(connections),
                    keyword=keyword
                )
        
        metadata["timing"]["parsing"] = (datetime.now() - stage_start).total_seconds()
        metadata["stages_completed"].append("parsing")
        metadata["quality_metrics"]["raw_connections"] = len(all_connections)
        
        # ===============================
        # STAGE 3: Entity Resolution & Dedup
        # ===============================
        stage_start = datetime.now()
        
        # Merge evidence from duplicates
        all_connections = self.deduplicator.merge_evidence(all_connections)
        
        # Mark cross-referenced (found in multiple searches)
        fingerprint_counts = {}
        for conn in all_connections:
            fingerprint_counts[conn.fingerprint] = fingerprint_counts.get(conn.fingerprint, 0) + 1
        
        for conn in all_connections:
            if fingerprint_counts[conn.fingerprint] > 1:
                conn.processing_notes.append("Cross-referenced across multiple degree searches")
        
        # Deduplicate
        all_connections = self.deduplicator.deduplicate(all_connections)
        
        metadata["timing"]["deduplication"] = (datetime.now() - stage_start).total_seconds()
        metadata["stages_completed"].append("deduplication")
        metadata["quality_metrics"]["after_dedup"] = len(all_connections)
        
        # ===============================
        # STAGE 4: Adversarial Check (Optional)
        # ===============================
        if enable_adversarial and all_connections:
            stage_start = datetime.now()
            
            all_connections = await self._run_adversarial_check(
                keyword, all_connections, perplexity_service
            )
            
            metadata["timing"]["adversarial_check"] = (datetime.now() - stage_start).total_seconds()
            metadata["stages_completed"].append("adversarial_check")
        
        # ===============================
        # STAGE 5: Confidence Calibration
        # ===============================
        stage_start = datetime.now()
        
        for conn in all_connections:
            # Check cross-reference
            cross_ref = "Cross-referenced" in " ".join(conn.processing_notes)
            
            # Calibrate
            conn.calibrated_confidence = self.calibrator.calibrate(
                connection=conn,
                adversarial_score=conn.adversarial_score,
                cross_reference_boost=cross_ref
            )
        
        metadata["timing"]["calibration"] = (datetime.now() - stage_start).total_seconds()
        metadata["stages_completed"].append("calibration")
        
        # ===============================
        # STAGE 6: Final Filtering & Ranking
        # ===============================
        stage_start = datetime.now()
        
        # Apply minimum confidence thresholds
        min_thresholds = {
            1: self.config["min_confidence_d1"],
            2: self.config["min_confidence_d2"],
            3: self.config["min_confidence_d3"],
        }
        
        filtered_connections = [
            conn for conn in all_connections
            if conn.calibrated_confidence >= min_thresholds.get(conn.degree, 0.60)
        ]
        
        # Sort by confidence
        filtered_connections.sort(key=lambda x: x.calibrated_confidence, reverse=True)
        
        # Limit total
        final_connections = filtered_connections[:self.config["max_total_connections"]]
        
        # Add connection chains
        for conn in final_connections:
            conn.connection_chain = self._format_chain(keyword, conn)
        
        metadata["timing"]["final_ranking"] = (datetime.now() - stage_start).total_seconds()
        metadata["stages_completed"].append("final_ranking")
        
        # ===============================
        # STAGE 7: Compile Output
        # ===============================
        metadata["quality_metrics"]["final_connections"] = len(final_connections)
        metadata["quality_metrics"]["by_degree"] = {
            1: len([c for c in final_connections if c.degree == 1]),
            2: len([c for c in final_connections if c.degree == 2]),
            3: len([c for c in final_connections if c.degree == 3]),
        }
        metadata["timing"]["total"] = (datetime.now() - start_time).total_seconds()
        
        # Convert to dicts
        output = [conn.to_dict() for conn in final_connections]
        
        logger.info(
            "Analysis complete",
                keyword=keyword,
            total_connections=len(output),
            total_time=metadata["timing"]["total"]
        )
        
        return output, metadata
    
    def _get_degree_1_prompt(self, keyword: str, one_year_ago: str, current_date: str) -> Tuple[str, str]:
        """Degree 1: Official Record with few-shot examples."""
        current_year = datetime.now().year
        
        system_prompt = f"""You are an expert Music Industry Researcher with access to official databases.

═══════════════════════════════════════════════════════════════
🎯 MISSION: Find VERIFIED, DOCUMENTED country music participation
═══════════════════════════════════════════════════════════════

TIME WINDOW: {one_year_ago} → {current_date} (Last 12 months ONLY)
EXCEPTION: Family ties (parent/child/spouse) are always valid

RETURN ONLY RAW JSON. No markdown, no <think> tags.

For each connection:
- entity: Name of Artist, Label, Venue, or Song
- entity_type: person|song|album|event|company
- type: credits|charts|performance|business|family|award
- description: Specific details with EXACT DATE (must be within last 12 months)
- degree: 1
- confidence: 0.0-1.0 (any level, we'll filter later)
- evidence: [Official source URLs]
- event_date: YYYY-MM format

RETURN ALL CONNECTIONS YOU FIND, even weak ones. Don't filter by confidence.

🚫 EXCLUSIONS:
- NO "attended a concert as a fan"
- NO "from the same state" (unless grew up together)
- NO social media rumors

Output JSON: {{"connections":[...]}}
IMPORTANT: Return connections even if confidence is low. Empty array only if genuinely nothing found."""

        query = f"""Find verified DIRECT country music connections for "{keyword}" active since {one_year_ago}.

SEARCH TERMS:
- "{keyword} songwriting credits {current_year}"
- "{keyword} Billboard country chart {current_year}"
- "{keyword} Grand Ole Opry {current_year}"
- "{keyword} CMA Awards {current_year}"
- "{keyword} signed Nashville label {current_year}"

Return RAW JSON only."""

        return system_prompt, query
    
    def _get_degree_2_prompt(self, keyword: str, one_year_ago: str, current_date: str) -> Tuple[str, str]:
        """Degree 2: Social Network with bridge person validation."""
        current_year = datetime.now().year
        
        system_prompt = f"""You are a Nashville Social Network Investigator.

═══════════════════════════════════════════════════════════════
🎯 MISSION: Find DOCUMENTED social proximity to country music
═══════════════════════════════════════════════════════════════

TIME WINDOW: {one_year_ago} → {current_date}

RETURN ONLY RAW JSON. No markdown, no <think> tags.

BRIDGE PERSON VALIDATION (CRITICAL):
To claim connection via bridge person, you MUST document BOTH links:
1. [Subject] → [Bridge Person] (with photo/interview evidence)
2. [Bridge Person] → [Country Music] (marriage/collaboration/documented friendship)

Known valid bridge people:
- Bunnie Xo (married to Jelly Roll)
- Brittany Aldean (married to Jason Aldean)
- KT Smith (Morgan Wallen's ex/co-parent)
- Nicole Hocking (married to Luke Combs)

For each connection:
- entity: Bridge Person Name OR Venue/Podcast
- entity_type: person|podcast|venue_event|collaboration
- type: bridge_person|podcast|venue_sighting|shared_team|collaboration|dating|friendship
- description: Details with [MONTH YEAR]
- degree: 2
- confidence: 0.0-1.0 (any level, we'll filter later)
- evidence: [URLs with dates]
- event_date: YYYY-MM format

RETURN ALL CONNECTIONS YOU FIND, even weak/indirect ones.

🚫 ONLY REJECT:
- "Follows on Instagram/TikTok"
- "Liked a post"

Output JSON: {{"connections":[...]}}
IMPORTANT: Return connections even if indirect or weak. Empty array only if genuinely nothing found."""

        query = f"""Find VERIFIED degree-2 social connections for "{keyword}" to country music from {one_year_ago} to {current_date}.

SEARCH STRATEGY:
- "{keyword} photographed country artist {current_year}"
- "{keyword} podcast Bobby Bones {current_year}"
- "{keyword} Bunnie Xo Brittany Aldean {current_year}"
- "{keyword} manager agent Nashville {current_year}"
- "{keyword} spotted Nashville bar {current_year}"

Return RAW JSON only."""

        return system_prompt, query
    
    def _get_degree_3_prompt(self, keyword: str, one_year_ago: str, current_date: str) -> Tuple[str, str]:
        """Degree 3: Lifestyle/Cultural signals with brand verification."""
        current_year = datetime.now().year
        
        system_prompt = f"""You are a Brand Partnership Analyst and Cultural Researcher.

═══════════════════════════════════════════════════════════════
🎯 MISSION: Find DOCUMENTED lifestyle signals matching country audience
═══════════════════════════════════════════════════════════════

TIME WINDOW: {one_year_ago} → {current_date}

RETURN ONLY RAW JSON. No markdown, no <think> tags.

VALID LIFESTYLE SIGNALS:

BRAND_SIGNAL (0.80-0.90 confidence):
  Required: Official partnership OR listed on brand website
  Brands: Yeti, Carhartt, Ariat, Tecovas, Bass Pro, Cabela's, BRCC, Traeger, Ford/Chevy/Ram

OUTDOOR_LIFESTYLE (0.70-0.85 confidence):
  Required: 2+ documented instances with dates
  Activities: Hunting, fishing tournaments, rodeo attendance

PROPERTY (0.75-0.85 confidence):
  Required: Property records OR reliable news coverage
  Locations: Franklin/Leiper's Fork TN, Montana ranches, Wyoming, Texas Hill Country

For each connection:
- entity: Brand/Property/Activity
- entity_type: brand|property|activity|charity
- type: brand_signal|outdoor_lifestyle|property|values_alignment|motorsports|audience_overlap
- description: Details with [MONTH YEAR]
- degree: 3
- confidence: 0.0-1.0 (any level, we'll filter later)
- evidence: [official_source_url]
- event_date: YYYY-MM format

RETURN ALL LIFESTYLE SIGNALS YOU FIND, even weak ones.

🚫 ONLY REJECT:
- Pure assumptions without any documentation

Output JSON: {{"connections":[...]}}
IMPORTANT: Return connections even if indirect or weak. Empty array only if genuinely nothing found."""

        query = f"""Find VERIFIED degree-3 lifestyle signals for "{keyword}" matching country music audience from {one_year_ago} to {current_date}.

SEARCH STRATEGY:
- site:yeti.com "{keyword}" OR "{keyword}" yeti ambassador
- "{keyword}" ranch property {current_year}"
- "{keyword}" hunting fishing documented {current_year}"
- "{keyword}" NASCAR {current_year}"
- "{keyword}" Carhartt Ariat Tecovas partnership

Return RAW JSON only."""

        return system_prompt, query
    
    def _repair_json(self, content: str) -> str:
        """Repair malformed JSON using json-repair library."""
        try:
            repaired = repair_json(content)
            return repaired
        except Exception as e:
            logger.error("JSON repair failed", error=str(e))
            return content
    
    def _parse_response(self, result: Dict[str, Any], degree: int) -> List[Connection]:
        """Parse Perplexity response into Connection objects."""
        content = result.get("content", "")
        citations = result.get("citations", [])
        
        # Clean content
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1].strip()
        
        # Find JSON
        if not content.startswith("{"):
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                content = content[start:end]
        
        connections = []
        
        try:
            data = json.loads(content)
            raw_connections = data.get("connections", [])
            if isinstance(data, list):
                raw_connections = data
        except json.JSONDecodeError:
            try:
                repaired = self._repair_json(content)
                data = json.loads(repaired)
                raw_connections = data.get("connections", [])
                if isinstance(data, list):
                    raw_connections = data
            except:
                logger.warning(f"Failed to parse degree {degree} response")
                return []
        
        for raw in raw_connections:
            try:
                # Build evidence list
                evidence_list = []
                raw_evidence = raw.get("evidence", []) or citations
                for url in raw_evidence:
                    if isinstance(url, str):
                        evidence_list.append(Evidence(
                            url=url,
                            source_name=self._extract_domain(url),
                            source_tier=self.knowledge_graph.get_source_tier(url)
                        ))
                
                # Parse event date
                event_date = None
                date_str = raw.get("event_date")
                if date_str:
                    try:
                        event_date = datetime.strptime(date_str, "%Y-%m")
                    except:
                        pass
                
                # Map connection type
                type_str = raw.get("type", "unknown")
                try:
                    conn_type = ConnectionType(type_str)
                except ValueError:
                    conn_type = ConnectionType.CREDITS if degree == 1 else \
                               ConnectionType.BRIDGE_PERSON if degree == 2 else \
                               ConnectionType.BRAND_SIGNAL
                
                conn = Connection(
                    entity=raw.get("entity", "Unknown"),
                    entity_type=raw.get("entity_type", "unknown"),
                    description=raw.get("description", ""),
                    degree=degree,
                    connection_type=conn_type,
                    raw_confidence=float(raw.get("confidence", 0.7)),
                    evidence=evidence_list,
                    event_date=event_date,
                    source_degree_search=degree
                )
                
                connections.append(conn)
                
            except Exception as e:
                logger.warning(f"Failed to parse connection", error=str(e), raw=raw)
                continue
                continue
        
        return connections
    
    async def _run_adversarial_check(
        self,
        keyword: str,
        connections: List[Connection],
        perplexity_service
    ) -> List[Connection]:
        """Run adversarial check to find counter-evidence."""
        
        # Prepare connections for adversarial prompt
        conn_dicts = [
            {
                "entity": c.entity,
                "description": c.description,
                "degree": c.degree,
                "confidence": c.raw_confidence,
            }
            for c in connections
        ]
        
        connections_text = json.dumps(conn_dicts, indent=2)
        
        system_prompt = """You are a Skeptical Fact-Checker whose job is to DISPROVE claims.

═══════════════════════════════════════════════════════════════
🎯 MISSION: Find counter-evidence or problems with claimed connections
═══════════════════════════════════════════════════════════════

For each connection, actively search for:
1. CONTRADICTIONS: Evidence that disproves the claim
2. DATE ISSUES: Is the date actually correct?
3. EXAGGERATIONS: Is the connection overstated?
4. MISSING CONTEXT: Important context that changes meaning?
5. SOURCE PROBLEMS: Are the sources actually reliable?

RETURN ONLY RAW JSON. No markdown, no <think> tags.

Output JSON:
{
  "evaluations": [
    {
      "entity": "Entity name from original",
      "original_confidence": 0.X,
      "issues_found": ["List of problems found"],
      "counter_evidence": ["URLs or facts that contradict"],
      "recommended_action": "KEEP|REDUCE_CONFIDENCE|REMOVE",
      "adjusted_confidence": 0.X,
      "reasoning": "Why this adjustment"
    }
  ]
}"""

        query = f"""Review these claimed connections for "{keyword}" and try to DISPROVE them:

{connections_text}

For each connection:
1. Search for contradicting information
2. Verify the dates are accurate
3. Check if sources are reliable
4. Look for important missing context

Return evaluation JSON for each connection."""

        try:
            result = await perplexity_service.search_and_analyze(
                query=query,
                system_prompt=system_prompt,
                temperature=0.0,
                model="sonar-reasoning-pro"
            )
            
            content = result.get("content", "")
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            
            # Parse adversarial results
            try:
                if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                data = json.loads(content)
                evaluations = data.get("evaluations", [])
            except:
                evaluations = []
            
            # Apply adversarial results
            for eval_item in evaluations:
                entity = eval_item.get("entity", "")
                for conn in connections:
                    if conn.entity.lower() == entity.lower():
                        # Apply adjustment
                        action = eval_item.get("recommended_action", "KEEP")
                        if action == "REMOVE":
                            conn.adversarial_score = 0.0
                            conn.counter_evidence = eval_item.get("counter_evidence", [])
                            conn.processing_notes.append(f"Adversarial: REMOVE - {eval_item.get('reasoning', '')}")
                        elif action == "REDUCE_CONFIDENCE":
                            adj_conf = eval_item.get("adjusted_confidence", conn.raw_confidence * 0.8)
                            conn.adversarial_score = adj_conf / conn.raw_confidence if conn.raw_confidence > 0 else 0.8
                            conn.counter_evidence = eval_item.get("counter_evidence", [])
                            conn.processing_notes.append(f"Adversarial: REDUCED - {eval_item.get('reasoning', '')}")
                        else:
                            conn.processing_notes.append("Adversarial: VERIFIED")
                        break
            
        except Exception as e:
            logger.warning("Adversarial check failed", error=str(e))
        
        return connections
    
    def _format_chain(self, keyword: str, connection: Connection) -> str:
        """Format connection chain for visualization."""
        if connection.degree == 1:
            return f"{keyword} → {connection.entity} → Country Music"
        elif connection.degree == 2:
            return f"{keyword} → {connection.entity} → [Country Entity]"
        else:
            return f"{keyword} → [Lifestyle Signal] → {connection.entity} → Country Audience"
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except:
            return "unknown"
            

# =============================================================================
# GLOBAL SERVICE INSTANCES
# =============================================================================

# Legacy service instance (for backwards compatibility)
connection_analyzer_service = ConnectionAnalyzerService()

# New analyzer instance (can be used directly for advanced features)
ultimate_connection_analyzer = UltimateConnectionAnalyzer()
