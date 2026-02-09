FROM python:3.12-slim

# Root Dockerfile — delegates to decisiongraph-complete service
# Python 3.12 removes f-string backslash restriction (PEP 701)

WORKDIR /app

# Copy requirements first for caching
COPY decisiongraph-complete/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY decisiongraph-complete/ .

# Purge any stale bytecode
RUN find /app -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true && \
    find /app -name '*.pyc' -delete 2>/dev/null || true

# Build-time syntax gate — fails the build if report package has errors
RUN find service/routers/report -name '*.py' -exec python -m py_compile {} + && \
    python -c "from service.routers.report import router, REPORT_MODULE_VERSION; print(f'report package OK — {REPORT_MODULE_VERSION}')"

# Log what we actually shipped
RUN echo "=== DEPLOYED FILE IDENTITY ===" && \
    head -2 service/routers/report/__init__.py && \
    find service/routers/report -name '*.py' | xargs wc -l && \
    python -c "print('Python version:'); import sys; print(sys.version)"

# Verify React dashboard is present
RUN if [ -f service/static/dashboard/index.html ]; then \
      echo "=== Dashboard SPA ===" && \
      ls -la service/static/dashboard/ && \
      ls -la service/static/dashboard/assets/ && \
      echo "Dashboard SPA verified OK"; \
    else \
      echo "WARNING: Dashboard SPA not found at service/static/dashboard/"; \
    fi

# Environment
ENV PYTHONPATH=/app:/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn service.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
