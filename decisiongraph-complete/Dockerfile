FROM python:3.11-slim

WORKDIR /app

# Cache bust to avoid stale COPY layers on rebuilds.
ARG CACHE_BUST=1
RUN echo "Cache bust: ${CACHE_BUST}"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set Python path for src imports
ENV PYTHONPATH=/app:/app/src
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "uvicorn service.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
