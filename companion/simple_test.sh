#!/bin/bash
echo "Infrastructure:"
curl -sf http://localhost:18000/health && echo " Gateway: OK" || echo " Gateway: FAIL"
curl -sf http://localhost:18002/health && echo " Embedding: OK" || echo " Embedding: FAIL"
docker exec companion_postgres psql -U companion -d companion_db -c "SELECT 1" > /dev/null 2>&1 && echo " Database: OK" || echo " Database: FAIL"

echo ""
echo "API Endpoints:"
curl -sf http://localhost:18000/api/admin/admin/users > /dev/null && echo " Admin API: OK" || echo " Admin API: FAIL"

echo ""
echo "Chat Test:"
curl -s -X POST http://localhost:18000/api/chat/chat/message -H "Content-Type: application/json" -d '{"user_id":"default_user","message":"hi"}' | head -c 200
