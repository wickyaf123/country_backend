#!/bin/bash

# Test script for Hybrid AI Strategy with 1 keyword
# Usage: ./test_hybrid_ai.sh

BASE_URL="http://localhost:8000"

echo ""
echo "======================================================================"
echo "HYBRID AI STRATEGY TEST - Single Keyword"
echo "======================================================================"
echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Step 1: Trigger pipeline
echo "📡 Triggering pipeline with keyword_limit=1..."
RESPONSE=$(curl -s -X POST "${BASE_URL}/api/v1/story-intelligence/manual-trigger?timeframe=24&keyword_limit=1")

if [ $? -ne 0 ]; then
    echo "❌ Failed to trigger pipeline"
    exit 1
fi

RUN_ID=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])")
ESTIMATED_TIME=$(echo $RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['estimated_time'])")

echo "✅ Pipeline started: $RUN_ID"
echo "   Estimated time: $ESTIMATED_TIME"
echo ""

# Step 2: Monitor progress
echo "⏳ Monitoring progress (checking every 5 seconds)..."
echo ""

START_TIME=$(date +%s)
LAST_STATUS=""

while true; do
    sleep 5
    
    # Check status
    STATUS_RESPONSE=$(curl -s "${BASE_URL}/api/v1/story-intelligence/pipeline-status/${RUN_ID}")
    CURRENT_STATUS=$(echo $STATUS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
    PROGRESS=$(echo $STATUS_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['progress'])")
    
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    # Print progress if changed
    if [ "$CURRENT_STATUS" != "$LAST_STATUS" ]; then
        echo "[${ELAPSED}s] Status: $CURRENT_STATUS - $PROGRESS"
        LAST_STATUS=$CURRENT_STATUS
    fi
    
    # Check if done
    if [ "$CURRENT_STATUS" = "completed" ] || [ "$CURRENT_STATUS" = "failed" ]; then
        echo ""
        echo "======================================================================"
        echo "Pipeline $(echo $CURRENT_STATUS | tr '[:lower:]' '[:upper:]')"
        echo "======================================================================"
        echo "Total time: ${ELAPSED} seconds ($((ELAPSED / 60)) minutes)"
        echo ""
        
        if [ "$CURRENT_STATUS" = "completed" ]; then
            echo "✅ Test completed successfully!"
            echo ""
            echo "To verify Hybrid AI usage, check backend logs for:"
            echo "   - 'Searching Degree 1, model=sonar-reasoning-pro'"
            echo "   - 'Searching Degree 2, model=sonar-deep-research'"
            echo "   - 'Searching Degree 3, model=sonar-deep-research'"
        else
            echo "❌ Pipeline failed. Check backend logs for details."
        fi
        
        break
    fi
done

echo ""







