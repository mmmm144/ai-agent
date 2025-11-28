#!/bin/bash
# Script để run server trong background với nohup

cd "$(dirname "$0")"

echo "🚀 Starting VNStock Agent API server..."

# Kill process cũ nếu có (port 8002)
lsof -ti:8002 | xargs kill -9 2>/dev/null

# Run server trong background
nohup python run_server.py > server.log 2>&1 &

SERVER_PID=$!
echo "✅ Server started with PID: $SERVER_PID"
echo "📝 Log file: server.log"
echo "🔗 API: http://localhost:8002"
echo ""
echo "To stop: kill $SERVER_PID  OR  lsof -ti:8002 | xargs kill -9"
echo "To view logs: tail -f server.log"
