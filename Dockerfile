# HPS SVT Tracker - Docker Image
# Multi-stage build for smaller final image

# =============================================================================
# Build stage
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for IV analysis and plotting
RUN pip install --no-cache-dir \
    pandas>=2.0 \
    openpyxl>=3.0 \
    numpy>=1.24

# =============================================================================
# Production stage
# =============================================================================
FROM python:3.11-slim

# Labels
LABEL maintainer="HPS Collaboration"
LABEL description="HPS SVT Component Tracker - Web Interface"
LABEL version="0.1.0"

# Create non-root user for security
RUN groupadd -r svttracker && useradd -r -g svttracker svttracker

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # For matplotlib
    libfreetype6 \
    libpng16-16 \
    # For general operations
    tini \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=svttracker:svttracker . .

# Install the application package
RUN pip install --no-cache-dir -e .

# Create directories for data persistence
RUN mkdir -p /data/db /data/test_data && \
    chown -R svttracker:svttracker /data

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SVT_DB_PATH=/data/db/svt_components.db \
    SVT_DATA_DIR=/data/test_data \
    FLASK_ENV=production

# Expose port
EXPOSE 5000

# Switch to non-root user
USER svttracker

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run with gunicorn
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "web.app:create_app()"]
