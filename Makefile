# VoteBem Django Application Makefile
# Simplifies Docker operations and development workflow

.PHONY: help build up down restart logs shell test clean dev prod deploy backup restore

# Default target
help:
	@echo "VoteBem Django Application - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  dev          - Start development environment"
	@echo "  dev-build    - Build and start development environment"
	@echo "  dev-down     - Stop development environment"
	@echo "  dev-logs     - View development logs"
	@echo "  dev-shell    - Access development container shell"
	@echo ""
	@echo "Production:"
	@echo "  prod         - Start production environment"
	@echo "  prod-build   - Build and start production environment"
	@echo "  prod-down    - Stop production environment"
	@echo "  prod-logs    - View production logs"
	@echo "  deploy       - Deploy to production"
	@echo ""
	@echo "Database:"
	@echo "  migrate      - Run database migrations"
	@echo "  makemigrations - Create new migrations"
	@echo "  superuser    - Create Django superuser"
	@echo "  dbshell      - Access database shell"
	@echo "  backup       - Create database backup"
	@echo "  restore      - Restore database from backup"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  test         - Run tests"
	@echo "  coverage     - Run tests with coverage"
	@echo "  lint         - Run code linting"
	@echo "  format       - Format code with black"
	@echo "  check        - Run all quality checks"
	@echo ""
	@echo "Utilities:"
	@echo "  clean        - Clean up containers and volumes"
	@echo "  logs         - View all logs"
	@echo "  status       - Show container status"
	@echo "  shell        - Access web container shell"
	@echo "  collectstatic - Collect static files"
	@echo ""

# Development Environment
dev:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Development environment started at http://localhost:8000"

dev-build:
	docker-compose -f docker-compose.dev.yml up --build -d
	@echo "Development environment built and started at http://localhost:8000"

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-shell:
	docker-compose -f docker-compose.dev.yml exec web bash

# Production Environment
prod:
	docker-compose up -d
	@echo "Production environment started"

prod-build:
	docker-compose up --build -d
	@echo "Production environment built and started"

prod-down:
	docker-compose down

prod-logs:
	docker-compose logs -f

deploy:
	@echo "Deploying to production..."
	git pull origin main
	docker-compose build --no-cache
	docker-compose up -d
	docker-compose exec web python manage.py migrate
	docker-compose exec web python manage.py collectstatic --noinput
	@echo "Deployment completed"

# Database Operations
migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

superuser:
	docker-compose exec web python manage.py createsuperuser

dbshell:
	docker-compose exec db psql -U votebem_user -d votebem_db

backup:
	@echo "Creating database backup..."
	mkdir -p backups
	docker-compose exec -T db pg_dump -U votebem_user votebem_db | gzip > backups/backup_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "Backup created in backups/ directory"

restore:
	@read -p "Enter backup file path: " backup_file; \
	gunzip -c $$backup_file | docker-compose exec -T db psql -U votebem_user -d votebem_db

# Testing & Quality
test:
	docker-compose -f docker-compose.dev.yml exec web python manage.py test

coverage:
	docker-compose -f docker-compose.dev.yml exec web coverage run --source='.' manage.py test
	docker-compose -f docker-compose.dev.yml exec web coverage report
	docker-compose -f docker-compose.dev.yml exec web coverage html
	@echo "Coverage report generated in htmlcov/"

lint:
	docker-compose -f docker-compose.dev.yml exec web flake8 .

format:
	docker-compose -f docker-compose.dev.yml exec web black .
	docker-compose -f docker-compose.dev.yml exec web isort .

check: lint test
	@echo "All quality checks completed"

# Utilities
clean:
	@echo "Cleaning up containers and volumes..."
	docker-compose down -v --remove-orphans
	docker-compose -f docker-compose.dev.yml down -v --remove-orphans
	docker system prune -f
	@echo "Cleanup completed"

logs:
	docker-compose logs -f

status:
	@echo "=== Container Status ==="
	docker-compose ps
	@echo ""
	@echo "=== System Resources ==="
	docker stats --no-stream

shell:
	docker-compose exec web bash

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

# Health Check
health:
	@echo "Checking application health..."
	@curl -f http://localhost/health/ && echo "\nApplication is healthy!" || echo "\nApplication health check failed!"

# Quick Setup
setup-dev:
	@echo "Setting up development environment..."
	cp .env.example .env.dev
	@echo "Please edit .env.dev with your development settings"
	make dev-build
	make migrate
	@echo "Development environment ready!"

setup-prod:
	@echo "Setting up production environment..."
	cp .env.example .env
	@echo "Please edit .env with your production settings"
	make prod-build
	make migrate
	@echo "Production environment ready!"

# Monitoring
monitor:
	@echo "=== Application Status ==="
	make health
	@echo ""
	@echo "=== Container Status ==="
	docker-compose ps
	@echo ""
	@echo "=== Recent Logs ==="
	docker-compose logs --tail=20

# Update
update:
	@echo "Updating application..."
	git pull origin main
	docker-compose build --no-cache
	docker-compose up -d
	make migrate
	make collectstatic
	@echo "Application updated successfully!"

# Development helpers
django-shell:
	docker-compose exec web python manage.py shell

flush-db:
	@read -p "Are you sure you want to flush the database? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker-compose exec web python manage.py flush --noinput

reset-db:
	@read -p "Are you sure you want to reset the database? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker-compose down -v
	docker-compose up -d db
	sleep 10
	make migrate
	@echo "Database reset completed"

# SSL Setup (for production)
ssl-setup:
	@read -p "Enter your domain name: " domain; \
	read -p "Enter your email: " email; \
	sudo certbot --nginx -d $$domain -d www.$$domain --email $$email --agree-tos --non-interactive
	mkdir -p ssl
	sudo cp /etc/letsencrypt/live/$$domain/fullchain.pem ssl/cert.pem
	sudo cp /etc/letsencrypt/live/$$domain/privkey.pem ssl/key.pem
	sudo chown $$USER:$$USER ssl/*.pem
	docker-compose restart nginx
	@echo "SSL certificate configured successfully!"

# Performance testing
load-test:
	@echo "Running basic load test..."
	@command -v ab >/dev/null 2>&1 || { echo "Apache Bench (ab) is required for load testing. Install with: sudo apt-get install apache2-utils"; exit 1; }
	ab -n 100 -c 10 http://localhost/

# Security scan
security-scan:
	@echo "Running security scan..."
	docker-compose -f docker-compose.dev.yml exec web python manage.py check --deploy

# Documentation
docs:
	@echo "Opening documentation..."
	@command -v xdg-open >/dev/null 2>&1 && xdg-open DOCKER_README.md || open DOCKER_README.md || echo "Please open DOCKER_README.md manually"

# Install development dependencies
install-dev-deps:
	@echo "Installing development dependencies..."
	@command -v pre-commit >/dev/null 2>&1 || pip install pre-commit
	pre-commit install
	@echo "Development dependencies installed"