# DecisionGraph Engine
# Bank-grade AML/KYC decision engine
#
# Build: docker build -t decisiongraph:2.1.1 --build-arg GIT_SHA=$(git rev-parse --short HEAD) -f docker/Dockerfile .
# Run:   docker run -p 8000:8000 decisiongraph:2.1.1

FROM python:3.11-slim AS base

# Build arguments
ARG GIT_SHA=unknown

# Labels
LABEL org.opencontainers.image.title="DecisionGraph"
LABEL org.opencontainers.image.description="Bank-grade AML/KYC Decision Engine"
LABEL org.opencontainers.image.version="2.1.1"
LABEL org.opencontainers.image.vendor="DecisionGraph"
LABEL org.opencontainers.image.revision="${GIT_SHA}"

# Environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV DG_ENGINE_VERSION=2.1.1
ENV DG_POLICY_VERSION=1.0.0
ENV DG_ENGINE_COMMIT=${GIT_SHA}

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application
COPY src/ src/
COPY service/ service/
COPY cli/ cli/
COPY schemas/ schemas/

# Non-root user
RUN useradd -m -u 1000 decisiongraph && \
    chown -R decisiongraph:decisiongraph /app
USER decisiongraph

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run service
CMD ["python", "-m", "uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000"]
