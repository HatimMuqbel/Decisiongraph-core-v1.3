FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/src
ENV PORT=8000

# Run - use shell form to expand $PORT
CMD uvicorn service.main:app --host 0.0.0.0 --port $PORT
