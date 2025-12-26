"""AI-powered content bucket classifier for Country Rebel."""

import structlog
from typing import Dict, List
from services.openai_service import openai_service

logger = structlog.get_logger()


class BucketClassifierService:
    """Classifies connections into Country Rebel content buckets."""
    
    COUNTRY_REBEL_BUCKETS = [
        "Artist News",
        "Viral Moments",
        "Lifestyle/Culture",
        "Awards/Events",
        "Emerging Artists",
        "Legacy/Heritage",
        "Feel-Good Stories",
        "Patriotic Content",
        "Listicles",
        "News Aggregation",
        "Interviews/Profiles"
    ]
    
    def classify_connection(self, connection: Dict) -> str:
        """
        Classify connection into Country Rebel content bucket.
        Uses rule-based + AI hybrid approach for accuracy and speed.
        
        Args:
            connection: Connection dict with type, description, entity
            
        Returns:
            Bucket name from COUNTRY_REBEL_BUCKETS
        """
        description = connection.get('description', '').lower()
        conn_type = connection.get('type', '').lower()
        entity = connection.get('entity', '').lower()
        
        # Rule-based classification (fast path)
        
        # Artist News
        if conn_type == 'artist' or any(word in description for word in [
            'album', 'tour', 'single', 'release', 'record', 'song'
        ]):
            return "Artist News"
        
        # Viral Moments
        if conn_type == 'viral' or any(word in description for word in [
            'viral', 'tiktok', 'trending', 'instagram', 'social media', 'video'
        ]):
            return "Viral Moments"
        
        # Patriotic Content
        if conn_type == 'patriotic' or any(word in description for word in [
            'military', 'veteran', 'patriotic', 'flag', 'anthem', 'troops', 'army', 'navy'
        ]):
            return "Patriotic Content"
        
        # Awards/Events
        if conn_type == 'event' or any(word in description for word in [
            'award', 'cma', 'acm', 'grammy', 'festival', 'concert', 'ceremony'
        ]):
            return "Awards/Events"
        
        # Lifestyle/Culture
        if any(word in description for word in [
            'faith', 'church', 'prayer', 'family', 'marriage', 'children', 'health'
        ]):
            return "Lifestyle/Culture"
        
        # Legacy/Heritage
        if any(word in description for word in [
            'legacy', 'heritage', 'classic', 'traditional', 'history', 'pioneer'
        ]):
            return "Legacy/Heritage"
        
        # Feel-Good Stories
        if any(word in description for word in [
            'kindness', 'charity', 'donation', 'help', 'support', 'fundraiser', 'gofundme'
        ]):
            return "Feel-Good Stories"
        
        # Emerging Artists
        if any(word in description for word in [
            'new artist', 'rising', 'emerging', 'debut', 'unsigned', 'discovery'
        ]):
            return "Emerging Artists"
        
        # Interviews/Profiles
        if any(word in description for word in [
            'interview', 'profile', 'exclusive', 'behind the scenes', 'personal story'
        ]):
            return "Interviews/Profiles"
        
        # Listicles (geographic, rankings)
        if any(word in description for word in [
            'texas', 'tennessee', 'nashville', 'top 10', 'best', 'list'
        ]):
            return "Listicles"
        
        # Default fallback
        return "News Aggregation"
    
    async def classify_connection_ai(self, connection: Dict) -> str:
        """
        Use OpenAI to classify edge cases that don't match rules.
        More expensive but more accurate for ambiguous cases.
        
        Args:
            connection: Connection dict with type, description, entity
            
        Returns:
            Bucket name from COUNTRY_REBEL_BUCKETS
        """
        try:
            prompt = f"""Classify this country music connection into ONE of these content buckets:

{', '.join(self.COUNTRY_REBEL_BUCKETS)}

Connection Details:
- Type: {connection.get('type', 'N/A')}
- Entity: {connection.get('entity', 'N/A')}
- Description: {connection.get('description', 'N/A')}

Respond with ONLY the bucket name, nothing else."""

            response = await openai_service.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=20
            )
            
            bucket = response.strip()
            
            # Validate bucket
            if bucket in self.COUNTRY_REBEL_BUCKETS:
                logger.info("AI classified connection", bucket=bucket, entity=connection.get('entity'))
                return bucket
            else:
                logger.warning("AI returned invalid bucket", response=response)
                return "News Aggregation"
                
        except Exception as e:
            logger.error("AI classification failed", error=str(e))
            return "News Aggregation"
    
    def classify_batch(self, connections: List[Dict]) -> List[Dict]:
        """
        Classify a batch of connections and add 'bucket' field.
        
        Args:
            connections: List of connection dicts
            
        Returns:
            Same list with 'country_rebel_bucket' field added
        """
        for conn in connections:
            if 'country_rebel_bucket' not in conn:
                conn['country_rebel_bucket'] = self.classify_connection(conn)
        
        return connections


# Global instance
bucket_classifier_service = BucketClassifierService()


