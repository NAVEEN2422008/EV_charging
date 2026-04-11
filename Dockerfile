FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN pip install --no-cache-dir -e .

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Run Streamlit app for Hugging Face Spaces
# Streamlit automatically binds to 0.0.0.0 on port 7860
CMD ["streamlit", "run", "app.py", "--server.port", "7860", "--server.address", "0.0.0.0", "--server.enableXsrfProtection=false"]
