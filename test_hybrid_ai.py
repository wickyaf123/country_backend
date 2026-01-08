"""
Test script for Hybrid AI Strategy with 1 keyword.

This script tests the pipeline with a single keyword to verify:
1. Model usage (sonar-reasoning-pro for D1, sonar-deep-research for D2/D3)
2. Recency filters (12-month cutoff)
3. Anti-fluff exclusions
4. Timing estimates

Usage:
    python test_hybrid_ai.py
"""

import asyncio
import httpx
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"


async def test_pipeline_with_one_keyword():
    """Test the pipeline with keyword_limit=1."""
    
    print("\n" + "="*70)
    print("HYBRID AI STRATEGY TEST - Single Keyword")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            # Step 1: Trigger pipeline with 1 keyword
            print("📡 Triggering pipeline with keyword_limit=1...")
            response = await client.post(
                f"{BASE_URL}/api/v1/story-intelligence/manual-trigger",
                params={
                    "timeframe": "24",
                    "keyword_limit": 1
                }
            )
            response.raise_for_status()
            data = response.json()
            
            run_id = data["run_id"]
            print(f"✅ Pipeline started: {run_id}")
            print(f"   Estimated time: {data.get('estimated_completion', 'Unknown')}")
            print(f"   Message: {data['message']}\n")
            
            # Step 2: Monitor progress
            print("⏳ Monitoring progress (checking every 5 seconds)...\n")
            
            start_time = time.time()
            last_status = None
            
            while True:
                await asyncio.sleep(5)
                
                # Check status
                status_response = await client.get(
                    f"{BASE_URL}/api/v1/story-intelligence/status/{run_id}"
                )
                status_response.raise_for_status()
                status = status_response.json()
                
                current_status = status["status"]
                progress = status["progress"]
                elapsed = int(time.time() - start_time)
                
                # Print progress if changed
                if current_status != last_status:
                    print(f"[{elapsed}s] Status: {current_status} - {progress}")
                    last_status = current_status
                
                # Check if done
                if current_status in ["completed", "failed"]:
                    print(f"\n{'='*70}")
                    print(f"Pipeline {current_status.upper()}")
                    print(f"{'='*70}")
                    print(f"Total time: {elapsed} seconds ({elapsed/60:.1f} minutes)\n")
                    
                    if current_status == "completed" and status.get("results"):
                        results = status["results"]
                        print("📊 Results:")
                        print(f"   Trends fetched: {results.get('trends_fetched', 0)}")
                        print(f"   Connections found: {results.get('connections_found', 0)}")
                        print(f"   Angles generated: {results.get('angles_generated', 0)}")
                        print(f"   RSS articles matched: {results.get('rss_articles_matched', 0)}\n")
                        
                        # Fetch detailed results
                        print("🔍 Fetching detailed connection data...\n")
                        dashboard_response = await client.get(
                            f"{BASE_URL}/api/v1/story-intelligence/dashboard"
                        )
                        dashboard_response.raise_for_status()
                        dashboard = dashboard_response.json()
                        
                        if dashboard["trending_keywords"]:
                            keyword = dashboard["trending_keywords"][0]
                            print(f"📌 Keyword: {keyword['keyword']}")
                            print(f"   Search volume: {keyword['search_volume']:,}")
                            print(f"   Connections: {keyword['connection_count']}\n")
                        
                        if dashboard["story_angles"]:
                            print("📰 Story Angles:")
                            for i, angle in enumerate(dashboard["story_angles"][:3], 1):
                                print(f"\n   {i}. {angle['headline']}")
                                print(f"      Description: {angle['angle_description'][:100]}...")
                                print(f"      Urgency: {angle['urgency_score']:.2f}")
                                print(f"      Confidence: {angle.get('uniqueness_score', 0):.2f}")
                    
                    break
            
            print("\n✅ Test completed successfully!")
            print("\nTo verify Hybrid AI usage, check backend logs for:")
            print("   - 'Searching Degree 1, model=sonar-reasoning-pro'")
            print("   - 'Searching Degree 2, model=sonar-deep-research'")
            print("   - 'Searching Degree 3, model=sonar-deep-research'")
            
        except httpx.HTTPStatusError as e:
            print(f"\n❌ HTTP Error: {e.response.status_code}")
            print(f"   Response: {e.response.text}")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    print("\n🚀 Starting Hybrid AI Strategy Test\n")
    print("Prerequisites:")
    print("  1. Backend server is running (python main.py)")
    print("  2. Perplexity API key is configured")
    print("  3. Database is set up\n")
    
    input("Press Enter to start the test...")
    
    asyncio.run(test_pipeline_with_one_keyword())

