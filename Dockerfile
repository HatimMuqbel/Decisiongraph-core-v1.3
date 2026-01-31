FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY claimpilot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY claimpilot/ ./claimpilot/

# Set Python path for src imports
ENV PYTHONPATH=/app/claimpilot/src
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "cd claimpilot && uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
