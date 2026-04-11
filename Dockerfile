FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN pip install --no-cache-dir -e .

# Make startup script executable
RUN chmod +x /app/scripts/start.sh

# Expose ports: 5000 for API (OpenEnv), 7860 for Streamlit (HF Spaces)
EXPOSE 5000 7860

# Run startup script that begins both API server and Streamlit
CMD ["/app/scripts/start.sh"]
