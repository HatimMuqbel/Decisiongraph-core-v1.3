FROM python:3.11-slim

# v4: Force complete rebuild 2026-02-05
ARG CACHEBUST=4
RUN echo "Build version: ${CACHEBUST} - $(date)"

WORKDIR /app

# Copy everything first to bust cache on any file change
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Verify report.py is the fixed version (no f-string backslash)
RUN python -c "import ast; ast.parse(open('service/routers/report.py').read()); print('report.py syntax OK')"

# Set Python path for src imports
ENV PYTHONPATH=/app:/app/src
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "uvicorn service.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
