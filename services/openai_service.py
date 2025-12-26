"""OpenAI service for content generation."""

import asyncio
from typing import Dict, List, Optional
import structlog
from openai import AsyncOpenAI
from config import settings

logger = structlog.get_logger()


class OpenAIService:
    """Service for interacting with OpenAI API for content generation."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout
            )
    
    async def generate_angles(
        self,
        topic: str,
        context: Dict,
        competitor_coverage: List[str],
        research_data: Dict
    ) -> List[Dict]:
        """
        Generate multiple content angles for a topic.
        
        Args:
            topic: The main topic/entity
            context: Context data (sources, trends, social mentions)
            competitor_coverage: List of competitor article summaries
            research_data: Google search research results
            
        Returns:
            List of angle suggestions with strategy, title, hook, seo_keywords
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")
        
        logger.info("Generating content angles", topic=topic)
        
        # Build comprehensive prompt
        prompt = self._build_angle_prompt(
            topic, context, competitor_coverage, research_data
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert content strategist for Country Rebel, 
a country music news and entertainment site. Generate unique, engaging content angles 
that leverage gaps in competitor coverage while aligning with Country Rebel's voice: 
authentic, fan-focused, and culturally relevant to country music."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.openai_temperature,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            angles = self._parse_angles(content)
            
            logger.info(f"Generated {len(angles)} angles", topic=topic)
            return angles
            
        except Exception as e:
            logger.error("Error generating angles", error=str(e), topic=topic)
            raise
    
    async def generate_article(
        self,
        angle: Dict,
        topic: str,
        research_data: Dict,
        tone: str = "engaging",
        word_count: int = 800
    ) -> Dict:
        """
        Generate a complete article based on approved angle.
        
        Args:
            angle: Selected angle with title, hook, strategy
            topic: Main topic/entity
            research_data: Research facts and context
            tone: Article tone (engaging, professional, casual, etc.)
            word_count: Target word count
            
        Returns:
            Dict with article content, seo metadata, social snippets
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")
        
        logger.info("Generating article", topic=topic, angle=angle.get("title"))
        
        prompt = self._build_article_prompt(
            angle, topic, research_data, tone, word_count
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a professional country music journalist writing for Country Rebel.
Write engaging, well-researched articles that inform and entertain country music fans.
Use an authentic voice that resonates with the community while maintaining journalistic integrity.
Include proper sourcing, avoid speculation, and create compelling narratives."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=settings.openai_temperature,
                max_tokens=settings.openai_max_tokens
            )
            
            content = response.choices[0].message.content
            article_data = self._parse_article(content)
            
            logger.info("Article generated successfully", topic=topic)
            return article_data
            
        except Exception as e:
            logger.error("Error generating article", error=str(e), topic=topic)
            raise
    
    async def generate_social_posts(
        self,
        article_title: str,
        article_summary: str,
        article_url: str,
        platforms: List[str] = ["facebook", "twitter", "instagram"]
    ) -> Dict[str, str]:
        """
        Generate platform-specific social media posts.
        
        Args:
            article_title: Article headline
            article_summary: Brief article summary
            article_url: URL to article
            platforms: List of platforms to generate for
            
        Returns:
            Dict mapping platform to post content
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")
        
        logger.info("Generating social posts", platforms=platforms)
        
        prompt = f"""Generate engaging social media posts for this Country Rebel article:

Title: {article_title}
Summary: {article_summary}
URL: {article_url}

Create platform-specific posts for: {', '.join(platforms)}

Requirements:
- Facebook: 2-3 sentences, conversational, includes link
- Twitter/X: Under 280 chars, punchy, includes hashtags
- Instagram: Engaging caption, emoji, relevant hashtags, link in bio mention

Format as JSON:
{{
    "facebook": "...",
    "twitter": "...",
    "instagram": "..."
}}
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a social media manager for Country Rebel. Create engaging posts that drive traffic."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=500
            )
            
            import json
            content = response.choices[0].message.content
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            posts = json.loads(content)
            logger.info("Social posts generated", platforms=list(posts.keys()))
            return posts
            
        except Exception as e:
            logger.error("Error generating social posts", error=str(e))
            raise
    
    async def generate_newsletter_snippet(
        self,
        article_title: str,
        article_summary: str,
        article_url: str
    ) -> str:
        """
        Generate a newsletter snippet for an article.
        
        Args:
            article_title: Article headline
            article_summary: Brief summary
            article_url: URL to article
            
        Returns:
            Newsletter-formatted snippet
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")
        
        prompt = f"""Create a compelling newsletter snippet for this Country Rebel article:

Title: {article_title}
Summary: {article_summary}
URL: {article_url}

Requirements:
- 2-3 sentences maximum
- Creates curiosity and drives clicks
- Country music fan voice
- Include call-to-action

Format as plain text ready for newsletter."""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a newsletter writer for Country Rebel. Create compelling snippets that drive engagement."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=200
            )
            
            snippet = response.choices[0].message.content.strip()
            logger.info("Newsletter snippet generated")
            return snippet
            
        except Exception as e:
            logger.error("Error generating newsletter snippet", error=str(e))
            raise
    
    async def check_grammar_and_quality(self, content: str) -> Dict:
        """
        Check grammar and content quality.
        
        Args:
            content: Article content to check
            
        Returns:
            Dict with score, issues, suggestions
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")
        
        prompt = f"""Review this article for grammar, clarity, and quality:

{content}

Provide:
1. Overall quality score (0-100)
2. Grammar/spelling issues
3. Clarity improvements
4. Fact-check concerns
5. Tone consistency

Format as JSON:
{{
    "score": 85,
    "grammar_issues": [],
    "clarity_suggestions": [],
    "concerns": [],
    "overall_assessment": "..."
}}
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert editor reviewing content for Country Rebel."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            import json
            content = response.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            quality_report = json.loads(content)
            return quality_report
            
        except Exception as e:
            logger.error("Error checking quality", error=str(e))
            raise
    
    async def generate_seo_metadata(
        self,
        article_title: str,
        article_content: str,
        primary_keyword: str
    ) -> Dict:
        """
        Generate SEO-optimized metadata.
        
        Args:
            article_title: Article title
            article_content: Full article content
            primary_keyword: Primary keyword to target
            
        Returns:
            Dict with meta_title, meta_description, keywords, slug
        """
        if not self.client:
            raise ValueError("OpenAI client not initialized")
        
        prompt = f"""Generate SEO metadata for this Country Rebel article:

Title: {article_title}
Primary Keyword: {primary_keyword}
Content: {article_content[:500]}...

Create:
1. SEO-optimized meta title (50-60 chars, includes keyword)
2. Meta description (150-160 chars, compelling, includes keyword)
3. URL slug (lowercase, hyphens, keyword-rich)
4. 5-7 relevant keywords/phrases
5. Suggested internal linking keywords

Format as JSON."""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an SEO specialist optimizing content for Country Rebel."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            import json
            content = response.choices[0].message.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            seo_data = json.loads(content)
            return seo_data
            
        except Exception as e:
            logger.error("Error generating SEO metadata", error=str(e))
            raise
    
    def _build_angle_prompt(
        self,
        topic: str,
        context: Dict,
        competitor_coverage: List[str],
        research_data: Dict
    ) -> str:
        """Build prompt for angle generation."""
        prompt = f"""Generate {settings.content_angle_count} unique content angles for this country music topic:

TOPIC: {topic}

CONTEXT:
- RSS Sources: {context.get('rss_sources', 0)} mentions
- Social Mentions (Awario): {context.get('awario_count', 0)} mentions
- Google Trends: Spike of {context.get('trend_spike', 0)}%
- Competitor Coverage: {len(competitor_coverage)} articles

COMPETITOR ANGLES USED:
{chr(10).join(f"- {angle}" for angle in competitor_coverage[:10])}

RESEARCH INSIGHTS:
{chr(10).join(f"- {fact}" for fact in research_data.get('key_facts', [])[:15])}

REQUIREMENTS:
Generate {settings.content_angle_count} distinct angles using these strategies:
1. **News Angle**: Straight breaking news, first to report
2. **Gap Angle**: Cover what competitors missed
3. **SEO Angle**: Target high-value search terms
4. **Country Rebel Spin**: Unique perspective, behind-the-scenes, fan connection

For each angle, provide:
- strategy (news/gap/seo/spin)
- title (compelling, 50-70 chars)
- hook (first paragraph, grabs attention)
- seo_keywords (3-5 terms)
- unique_value (why this beats competitors)

Format as JSON array."""
        
        return prompt
    
    def _parse_angles(self, content: str) -> List[Dict]:
        """Parse angle generation response."""
        import json
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            angles = json.loads(content)
            if isinstance(angles, dict) and "angles" in angles:
                angles = angles["angles"]
            
            return angles if isinstance(angles, list) else []
        except Exception as e:
            logger.error("Error parsing angles", error=str(e))
            return []
    
    def _build_article_prompt(
        self,
        angle: Dict,
        topic: str,
        research_data: Dict,
        tone: str,
        word_count: int
    ) -> str:
        """Build prompt for article generation."""
        facts = research_data.get('key_facts', [])
        sources = research_data.get('sources', [])
        
        prompt = f"""Write a comprehensive country music article for Country Rebel:

ANGLE: {angle.get('title')}
HOOK: {angle.get('hook')}
STRATEGY: {angle.get('strategy')}
TARGET LENGTH: {word_count} words
TONE: {tone}

TOPIC: {topic}

RESEARCHED FACTS:
{chr(10).join(f"- {fact}" for fact in facts[:20])}

SOURCES TO CITE:
{chr(10).join(f"- {source}" for source in sources[:10])}

REQUIREMENTS:
1. Start with the provided hook (modify slightly if needed)
2. Include all key facts with proper attribution
3. Write in Country Rebel voice: authentic, fan-focused, engaging
4. Structure: Hook → Context → Main Story → Impact → Conclusion
5. Include quotes if available in research
6. Add cultural/historical context where relevant
7. Target {word_count} words (±100 words acceptable)
8. Use subheadings for readability
9. End with forward-looking statement or call-to-action
10. Cite sources inline (e.g., "according to [source]")

SEO KEYWORDS TO INCLUDE: {', '.join(angle.get('seo_keywords', []))}

Format as JSON:
{{
    "title": "Final headline",
    "subtitle": "Optional subtitle",
    "content": "Full article HTML with <h2>, <p>, <blockquote>, etc.",
    "excerpt": "2-sentence summary",
    "word_count": actual_count,
    "sources_cited": ["source1", "source2"]
}}
"""
        return prompt
    
    def _parse_article(self, content: str) -> Dict:
        """Parse article generation response."""
        import json
        import re
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Try standard JSON parsing first
            try:
                article = json.loads(content)
                return article
            except json.JSONDecodeError:
                # If that fails, try with more lenient parsing
                # Clean up common escape issues
                content_fixed = content.replace('\\"', '"').replace("\\'", "'")
                article = json.loads(content_fixed, strict=False)
                return article
                
        except Exception as e:
            logger.error("Error parsing article", error=str(e))
            # Try to extract at least the content as plain text
            # Look for common JSON field patterns
            title_match = re.search(r'"title":\s*"([^"]+)"', content)
            content_match = re.search(r'"content":\s*"([\s\S]+?)"(?=,\s*"|\s*})', content)
            
            return {
                "title": title_match.group(1) if title_match else "Generated Article",
                "content": content_match.group(1) if content_match else content[:1000],
                "excerpt": "",
                "word_count": len(content.split()) if content else 0,
                "sources_cited": []
            }


# Global service instance
openai_service = OpenAIService()

