#!/bin/bash
set -e

echo "Starting EV Charging Grid Environment services..."

# Start API server in background on port 5000
echo "Starting API server on port 5000..."
python api_server.py --host 0.0.0.0 --port 5000 &
API_PID=$!
echo "API server PID: $API_PID"

# Give API server a moment to start
sleep 2

# Check if API server started successfully
if ! ps -p $API_PID > /dev/null; then
    echo "ERROR: API server failed to start"
    exit 1
fi

# Start Streamlit app on port 7860 in foreground
echo "Starting Streamlit app on port 7860..."
streamlit run app.py --server.port 7860 --server.address 0.0.0.0 --server.enableXsrfProtection=false

# Cleanup on exit
cleanup() {
    echo "Shutting down services..."
    kill $API_PID 2>/dev/null || true
}
trap cleanup EXIT INT TERM
