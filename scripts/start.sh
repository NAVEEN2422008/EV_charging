#!/bin/bash
set -e

echo "Starting EV Charging Grid Environment services..."

# Start API server in background on port 5000
echo "Starting API server on port 5000..."
python api_server.py --host 0.0.0.0 --port 5000 > /tmp/api_server.log 2>&1 &
API_PID=$!
echo "API server PID: $API_PID"

# Give API server time to start
sleep 3

# Check if server is responding (health check)
echo "Checking API server health..."
if ! curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo "WARNING: API server health check failed, but continuing..."
    echo "API server logs:"
    cat /tmp/api_server.log || echo "No logs available"
fi

echo "API server started successfully!"

# Start Streamlit app on port 7860 in foreground
echo "Starting Streamlit app on port 7860..."
streamlit run app.py --server.port 7860 --server.address 0.0.0.0 --server.enableXsrfProtection=false

# Cleanup on exit
cleanup() {
    echo "Shutting down services..."
    kill $API_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM
