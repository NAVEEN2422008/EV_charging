FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy entire repository
COPY . /app

# Install package in editable mode
RUN pip install --no-cache-dir -e .

# Make startup script executable
RUN chmod +x /app/scripts/start.sh

# Expose ports: 5000 for API, 7860 for Streamlit
EXPOSE 5000 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Run startup script
CMD ["/app/scripts/start.sh"]
