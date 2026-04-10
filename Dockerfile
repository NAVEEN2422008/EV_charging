FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN pip install --no-cache-dir -e .

# Expose port 5000 for OpenEnv API server
EXPOSE 5000

# Run API server for OpenEnv validation
# (Streamlit dashboard available separately in app.py for development)
CMD ["python", "api_server.py", "--host", "0.0.0.0", "--port", "5000"]
