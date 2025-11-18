# Build stage
FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Install build dependencies for SQL Server ODBC driver
RUN apt-get update && apt-get install -y \
    curl \
    apt-transport-https \
    gnupg \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-workspace

# Copy application code
COPY . .

# Install the project
RUN uv sync --frozen

# Runtime stage
FROM python:3.11-slim AS runtime

# Install uv for runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install runtime dependencies including SQL Server ODBC driver
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    apt-transport-https \
    gnupg \
    unixodbc \
    && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1001 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    UV_SYSTEM_PYTHON=1

# Set working directory
WORKDIR /app

# Copy virtual environment and application from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app /app

# Remove any .env file that might have been copied
RUN rm -f .env

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Add metadata labels
LABEL maintainer="AAK-MBU" \
      version="2.10.1" \
      description="Process Dashboard API"

# Use exec form for proper signal handling
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]