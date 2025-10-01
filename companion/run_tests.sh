#!/bin/bash
# Comprehensive Test Suite for Companion System

set -e

echo "==================================================="
echo "  COMPANION SYSTEM - COMPREHENSIVE TEST SUITE"
echo "==================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

test_result() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAILED${NC}"
        ((FAILED++))
    fi
}

echo -e "${BLUE}=== 1. INFRASTRUCTURE TESTS ===${NC}"
echo ""

echo "1.1 Testing PostgreSQL..."
docker exec companion_postgres psql -U companion -d companion_db -c "SELECT version();" > /dev/null 2>&1
test_result

echo "1.2 Testing Qdrant..."
curl -sf http://localhost:16333/health > /dev/null 2>&1
test_result

echo "1.3 Testing Redis..."
docker exec companion_redis redis-cli ping > /dev/null 2>&1
test_result

echo ""
echo -e "${BLUE}=== 2. SERVICE HEALTH TESTS ===${NC}"
echo ""

echo "2.1 Testing Gateway Health..."
HEALTH=$(curl -s http://localhost:18000/health)
echo $HEALTH | grep -q "healthy"
test_result

echo "2.2 Testing Gateway Status..."
curl -sf http://localhost:18000/status > /dev/null 2>&1
test_result

echo "2.3 Testing Embedding Service..."
curl -sf http://localhost:18002/health > /dev/null 2>&1
test_result

echo "2.4 Testing Letta Service..."
curl -sf http://localhost:18283/ > /dev/null 2>&1
test_result

echo ""
echo -e "${BLUE}=== 3. DATABASE SCHEMA TESTS ===${NC}"
echo ""

echo "3.1 Checking user_profiles table..."
docker exec companion_postgres psql -U companion -d companion_db -c "\d user_profiles" > /dev/null 2>&1
test_result

echo "3.2 Checking personality_state table..."
docker exec companion_postgres psql -U companion -d companion_db -c "\d personality_state" > /dev/null 2>&1
test_result

echo "3.3 Checking interactions table..."
docker exec companion_postgres psql -U companion -d companion_db -c "\d interactions" > /dev/null 2>&1
test_result

echo ""
echo -e "${BLUE}=== 4. API ENDPOINT TESTS ===${NC}"
echo ""

echo "4.1 Testing Admin Users List..."
curl -sf http://localhost:18000/api/admin/admin/users > /dev/null 2>&1
test_result

echo "4.2 Testing System Stats..."
curl -sf http://localhost:18000/api/admin/admin/stats > /dev/null 2>&1
test_result

echo "4.3 Testing Personality Endpoint (default_user)..."
curl -sf http://localhost:18000/api/personality/personality/current/default_user > /dev/null 2>&1
test_result

echo ""
echo -e "${BLUE}=== 5. CHAT INTEGRATION TEST ===${NC}"
echo ""

echo "5.1 Sending test message to default_user..."
RESPONSE=$(curl -s -X POST http://localhost:18000/api/chat/chat/message \
  -H "Content-Type: application/json" \
  -d '{"user_id":"default_user","message":"Hello! Tell me a fun fact."}')

echo "Response: $RESPONSE" | head -c 200
echo "..."
echo $RESPONSE | grep -q "response" && echo -e "${GREEN}✓ PASSED${NC}" && ((PASSED++)) || (echo -e "${RED}✗ FAILED${NC}" && ((FAILED++)))

echo ""
echo -e "${BLUE}=== 6. MEMORY SYSTEM TEST ===${NC}"
echo ""

echo "6.1 Storing episodic memory..."
MEMORY_RESPONSE=$(curl -s -X POST http://localhost:18000/api/memory/memory/store/default_user \
  -H "Content-Type: application/json" \
  -d '{"content":"User mentioned they love hiking in the mountains","memory_type":"episodic","importance_score":0.8}')

echo $MEMORY_RESPONSE | grep -q "memory_id" && echo -e "${GREEN}✓ PASSED${NC}" && ((PASSED++)) || (echo -e "${RED}✗ FAILED${NC}" && ((FAILED++)))

echo "6.2 Searching memories..."
SEARCH_RESPONSE=$(curl -s -X POST http://localhost:18000/api/memory/memory/search/default_user \
  -H "Content-Type: application/json" \
  -d '{"query":"What does the user like to do?","limit":5}')

echo $SEARCH_RESPONSE | head -c 100
echo "..."
echo $SEARCH_RESPONSE | grep -q "memories" && echo -e "${GREEN}✓ PASSED${NC}" && ((PASSED++)) || (echo -e "${RED}✗ FAILED${NC}" && ((FAILED++)))

echo ""
echo -e "${BLUE}=== 7. BACKGROUND SERVICES TEST ===${NC}"
echo ""

echo "7.1 Checking scheduler status..."
curl -sf http://localhost:18000/api/admin/admin/scheduler/status > /dev/null 2>&1
test_result

echo "7.2 Checking background tasks..."
curl -sf http://localhost:18000/api/admin/admin/background/tasks > /dev/null 2>&1
test_result

echo ""
echo "==================================================="
echo -e "  TEST RESULTS: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo "==================================================="

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed successfully!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please check the output above.${NC}"
    exit 1
fi
