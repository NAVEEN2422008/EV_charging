#!/bin/bash
set -e

echo "Starting EV Charging Grid Environment services..."

# Start nginx in background
echo "Starting nginx reverse proxy..."
service nginx start || nginx -g "daemon off;" &
NGINX_PID=$!
sleep 2

# Start API server in background on port 5000
echo "Starting API server on port 5000..."
python /app/api_server.py --host 0.0.0.0 --port 5000 > /tmp/api_server.log 2>&1 &
API_PID=$!
echo "API server PID: $API_PID"

# Give API server time to start
sleep 3

# Simple health check
echo "Checking API server..."
max_retries=5
retry=0
while [ $retry -lt $max_retries ]; do
    if timeout 2 python -c "import requests; requests.get('http://localhost:5000/health')" > /dev/null 2>&1; then
        echo "✓ API server is responding"
        break
    fi
    retry=$((retry + 1))
    if [ $retry -lt $max_retries ]; then
        echo "  Retrying... ($retry/$max_retries)"
        sleep 1
    fi
done

if [ $retry -eq $max_retries ]; then
    echo "⚠ API server not responding, but continuing..."
    tail -n 10 /tmp/api_server.log 2>/dev/null || echo "  (check logs)"
fi

# Start Streamlit app on port 8501 in foreground
echo "Starting Streamlit app on port 8501..."
streamlit run /app/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.enableXsrfProtection=false \
    --logger.level=info

# Cleanup on exit
cleanup() {
    echo "Shutting down services..."
    kill $API_PID 2>/dev/null || true
    kill $NGINX_PID 2>/dev/null || true
    service nginx stop 2>/dev/null || true
}
trap cleanup EXIT INT TERM
