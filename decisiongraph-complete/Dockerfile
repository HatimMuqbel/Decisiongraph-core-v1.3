FROM python:3.12-slim

# v6: Python 3.12 — PEP 701 removes f-string backslash restriction
ARG CACHEBUST=6
RUN echo "Build version: ${CACHEBUST} - $(date)"

WORKDIR /app

# Copy application (filtered by .dockerignore)
COPY . .

# Purge any stale bytecode that survived
RUN find /app -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name '*.pyc' -delete 2>/dev/null || true

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ── Build-time syntax gate ──
# If report.py has ANY syntax error, the build fails and nothing deploys.
RUN python -c "\
import ast, sys; \
src = open('service/routers/report.py').read(); \
tree = ast.parse(src); \
lines = src.count(chr(10)) + 1; \
print(f'report.py: {lines} lines, syntax OK'); \
sys.exit(0)"

# Print file identity so deploy logs show exactly what shipped
RUN head -1 service/routers/report.py && wc -l service/routers/report.py

# Set Python path for src imports
ENV PYTHONPATH=/app:/app/src
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "uvicorn service.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
