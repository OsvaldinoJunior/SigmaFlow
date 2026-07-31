#!/bin/bash
# SigmaFlow Health Check Script
# =============================
# Used by Docker health checks and monitoring systems

set -e

API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-10}"

echo "🔍 SigmaFlow Health Check"
echo "========================="
echo "Target: $API_URL"
echo ""

# Function to check endpoint
check_endpoint() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}
    
    echo -n "Checking $name... "
    
    response=$(curl -s -w "\n%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null || echo -e "\n000")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$http_code" = "$expected_status" ]; then
        echo "✅ OK (HTTP $http_code)"
        return 0
    else
        echo "❌ FAILED (HTTP $http_code)"
        if [ -n "$body" ]; then
            echo "   Response: $body"
        fi
        return 1
    fi
}

# Function to check JSON response
check_json_field() {
    local name=$1
    local url=$2
    local field=$3
    local expected_value=$4
    
    echo -n "Checking $name ($field)... "
    
    response=$(curl -s --max-time "$TIMEOUT" "$url" 2>/dev/null || echo '{}')
    value=$(echo "$response" | jq -r ".$field // empty" 2>/dev/null || echo "")
    
    if [ "$value" = "$expected_value" ]; then
        echo "✅ OK ($field=$value)"
        return 0
    else
        echo "❌ FAILED ($field=$value, expected=$expected_value)"
        echo "   Full response: $response"
        return 1
    fi
}

# Track overall status
OVERALL_STATUS=0

# 1. Basic health endpoint
check_endpoint "Health endpoint" "$API_URL/health" 200 || OVERALL_STATUS=1

# 2. Detailed health info
check_json_field "Database status" "$API_URL/health" "database" "connected" || OVERALL_STATUS=1

# 3. API info endpoint
check_endpoint "Info endpoint" "$API_URL/api/v1/info" 200 || OVERALL_STATUS=1

# 4. Check version
check_json_field "API version" "$API_URL/api/v1/info" "version" "0.2.0" || OVERALL_STATUS=1

# 5. Check if database is accessible (via a simple query through API)
# This requires authentication, so we just verify the endpoint exists
check_endpoint "Projects endpoint (requires auth)" "$API_URL/api/v1/projects" 401 || OVERALL_STATUS=1

# 6. Check metrics endpoint if enabled
if [ "${METRICS_ENABLED:-true}" = "true" ]; then
    METRICS_PORT="${METRICS_PORT:-9090}"
    check_endpoint "Metrics endpoint" "http://localhost:$METRICS_PORT/metrics" 200 || true  # Non-critical
fi

echo ""
echo "========================="
if [ $OVERALL_STATUS -eq 0 ]; then
    echo "🎉 All health checks PASSED"
    exit 0
else
    echo "💥 Some health checks FAILED"
    exit 1
fi