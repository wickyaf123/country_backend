# Hybrid AI Strategy Implementation

## Overview

This implementation introduces a hybrid AI strategy that combines two Perplexity models:
- **sonar-reasoning-pro**: Fast, factual verification (Degree 1)
- **sonar-deep-research**: Deep, exhaustive research (Degrees 2 & 3)

Combined with strict 12-month recency filters and anti-fluff rules to eliminate weak connections.

## Changes Made

### 1. Connection Analyzer Service (`services/connection_analyzer_service.py`)

**Updated `_search_comprehensive_connections` method:**
- Added 12-month recency calculation using `timedelta`
- Updated all three system prompts with TIME CONSTRAINT sections
- Added STRICT EXCLUSIONS to Degree 2 and 3 prompts
- Implemented hybrid model configuration:
  - Degree 1: Always uses `sonar-reasoning-pro`
  - Degree 2 & 3: Use `sonar-deep-research` when `deep_research=True`
- Explicitly pass model parameter to Perplexity service

**Anti-Fluff Rules Added:**
- ❌ NO "Follows on Instagram" (Degree 2)
- ❌ NO "From the same state" (unless grew up together)
- ❌ NO "Likes a post"
- ❌ NO expired brand deals (Degree 3)
- ❌ NO casual one-time mentions
- ✅ MUST have physical meetings, collaborations, or official partnerships

### 2. Story Intelligence Service (`services/story_intelligence_service.py`)

**Updated `analyze_all_connections` method:**
- Reduced batch size from 50 to 5 (critical for deep-research rate limits)
- Enabled `deep_research=True` in all connection analysis calls
- Updated logging to show "Hybrid AI (Reasoning + Deep Research)" strategy
- Increased pause between batches from 2s to 3s

**Updated `run_hourly_intelligence_cycle` method:**
- Added `keyword_limit` parameter for testing
- Applied keyword limit when fetching trends

### 3. RSS Realtime Service (`services/rss_realtime_service.py`)

**Updated `_scrape_single_source` method:**
- Added 30-day cutoff date calculation
- Skip articles older than 30 days
- Ensures RSS articles match the 12-month connection recency

### 4. API Endpoint (`api/story_intelligence.py`)

**Updated `/manual-trigger` endpoint:**
- Added `keyword_limit` query parameter
- Passes limit to the service for testing purposes

## Performance Characteristics

### Timing
- **Old System**: ~2-3 minutes for 50 keywords (all reasoning-pro)
- **New System**: ~12 minutes for 50 keywords (hybrid strategy)
- **Single Keyword Test**: ~40-60 seconds

### Rate Limits
- `sonar-reasoning-pro`: 50 RPM (Degree 1 = safe)
- `sonar-deep-research`: 10 RPM (Degrees 2 & 3 = at limit with batch size 5)

### Cost
- Reasoning-pro: ~$0.005 per request
- Deep-research: ~$0.05 per request
- **Total per 50-keyword run**: ~$5.25

## Testing

### Method 1: Python Script (Recommended)

```bash
cd backend
python test_hybrid_ai.py
```

This script will:
1. Trigger pipeline with 1 keyword
2. Monitor progress in real-time
3. Display results and timing
4. Show what to look for in logs

### Method 2: Shell Script

```bash
cd backend
chmod +x test_hybrid_ai.sh
./test_hybrid_ai.sh
```

### Method 3: Manual API Call

```bash
# Start the pipeline
curl -X POST "http://localhost:8000/api/v1/story-intelligence/manual-trigger?timeframe=24&keyword_limit=1"

# Check status (replace RUN_ID with actual ID from response)
curl "http://localhost:8000/api/v1/story-intelligence/pipeline-status/RUN_ID"
```

### Method 4: Frontend UI

1. Open the Story Intelligence page
2. Click "Run Pipeline"
3. Monitor the progress in real-time
4. Check the connections graph and story angles

## Verification Checklist

After running the test, verify in backend logs:

✅ **Model Usage:**
```
Searching Degree 1, model=sonar-reasoning-pro
Searching Degree 2, model=sonar-deep-research
Searching Degree 3, model=sonar-deep-research
```

✅ **Recency Filters:**
- Connection descriptions mention recent dates (within last 12 months)
- RSS articles are from last 30 days

✅ **Anti-Fluff Working:**
- No connections like "follows on Instagram"
- No connections like "both from Texas"
- All connections have specific dates and evidence

✅ **Performance:**
- Degree 1 completes in 2-5 seconds
- Degrees 2 & 3 take 10-30 seconds each
- Total ~40-60 seconds for 1 keyword

## Example Output

**Good Connection (Accepted):**
```json
{
  "degree": 1,
  "type": "credits",
  "entity": "Morgan Wallen",
  "description": "Co-wrote 'Last Night' with Morgan Wallen in March 2024",
  "confidence": 0.95,
  "evidence": ["https://ascap.com/..."]
}
```

**Bad Connection (Rejected):**
```json
// This would be filtered out by anti-fluff rules:
{
  "degree": 2,
  "type": "social",
  "entity": "Luke Combs",
  "description": "Follows Luke Combs on Instagram",  // ❌ Meaningless
  "confidence": 0.3
}
```

## Rollback Plan

If costs are too high or performance is unacceptable:

1. Set `deep_research=False` in `story_intelligence_service.py` line 535:
```python
deep_research=False  # Falls back to reasoning-pro for all degrees
```

2. Increase batch size back to 10-20:
```python
batch_size = 10  # or 20
```

3. This will:
   - Reduce cost to ~$0.25 per run
   - Complete in ~2-3 minutes
   - But may miss some deep connections

## Monitoring

Watch for these metrics in your logs:
- `connections_found`: Should be fewer but higher quality
- `parsing_status`: Should be mostly "success"
- `model_used`: Verify hybrid usage
- Pipeline duration: ~12 minutes for 50 keywords

## Next Steps

1. Run the test with 1 keyword
2. Verify logs show correct model usage
3. Check that connections have recent dates
4. Run full pipeline with 50 keywords
5. Compare quality of connections vs. old system
6. Monitor costs and adjust if needed







