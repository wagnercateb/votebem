# After changing docker-compose.yml , use docker compose up -d to recreate the container. docker compose restart web does not apply changed environment or volume configuration.
# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set default environment variables for build
ENV DEBUG=False
ENV SECRET_KEY=build-time-secret-key
ENV ALLOWED_HOSTS=localhost
ENV DB_NAME=votebem_db
ENV DB_USER=votebem_user
ENV DB_PASSWORD=build_password
ENV DB_HOST=localhost
ENV DB_PORT=3306
ENV REDIS_URL=redis://localhost:6379/0
ENV EMAIL_HOST=localhost
ENV EMAIL_PORT=587
ENV EMAIL_USE_TLS=True
ENV EMAIL_HOST_USER=
ENV EMAIL_HOST_PASSWORD=
ENV DEFAULT_FROM_EMAIL=noreply@votebem.com
ENV USE_HTTPS=False
ENV CORS_ALLOWED_ORIGINS=
ENV ENABLE_REMOTE_DEBUG=False

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-mysql-client \
        build-essential \
        pkg-config \
        libmariadb-dev \
        libmariadb-dev-compat \
        zlib1g-dev \
        libjpeg-dev \
        libpng-dev \
        curl \
        nano \
        git \
        && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
ENV MARIADB_CONFIG=/usr/bin/mariadb_config
RUN pip install --no-cache-dir -r requirements.txt

# Install additional production dependencies
RUN pip install --no-cache-dir \
    gunicorn==21.2.0 \
    whitenoise==6.5.0 \
    django-cors-headers==4.3.1 \
    debugpy==1.8.0

# Copy project
COPY . /app/

# Copy images to specific folders


# Create necessary directories
# Ensure RAG-related folders exist to avoid runtime errors when saving embeddings/respostas_ia
RUN mkdir -p /app/staticfiles /app/logs \
    && mkdir -p /app/docs/nao_versionados/embeddings \
    && mkdir -p /app/docs/nao_versionados/respostas_ia

# Collect static files using build settings (optimized for Docker build)
ENV DJANGO_SETTINGS_MODULE=votebem.settings.build
RUN python manage.py collectstatic --noinput --settings=votebem.settings.build

# Set production settings for runtime
ENV DJANGO_SETTINGS_MODULE=votebem.settings.production

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
RUN chmod -R 755 /app/logs
USER appuser

# Expose port
EXPOSE 8000
EXPOSE 5678

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "votebem.wsgi:application"]