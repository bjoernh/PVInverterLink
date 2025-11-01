#!/bin/bash

# Production Environment Deployment Script
# Usage: ./deploy-prod.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT="prod"
COMPOSE_FILE="deployment/docker-compose.${ENVIRONMENT}.yml"
# Default to 'prod' tag for production, or use environment variable
export IMAGE_TAG="${IMAGE_TAG:-prod}"

echo -e "${RED}========================================${NC}"
echo -e "${RED}  PRODUCTION DEPLOYMENT${NC}"
echo -e "${RED}========================================${NC}"
echo ""
echo -e "${RED}WARNING: This will deploy to PRODUCTION!${NC}"
echo -e "${YELLOW}Image Tag: ${IMAGE_TAG}${NC}"
echo ""
read -p "Are you sure you want to continue? Type 'yes' to proceed: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled"
    exit 0
fi

# Check if .env.prod exists
if [ ! -f ".env.${ENVIRONMENT}" ]; then
    echo -e "${RED}Error: .env.${ENVIRONMENT} not found!${NC}"
    echo "Please copy .env.${ENVIRONMENT}.example to .env.${ENVIRONMENT} and configure it."
    exit 1
fi

# Security checks
echo ""
echo -e "${YELLOW}Running security checks...${NC}"

# Check if COOKIE_SECURE is set to True
if ! grep -q "COOKIE_SECURE=True" .env.${ENVIRONMENT}; then
    echo -e "${RED}WARNING: COOKIE_SECURE is not set to True!${NC}"
    echo "This is required for production. Set COOKIE_SECURE=True in .env.prod"
    read -p "Continue anyway? (not recommended) Type 'yes': " CONTINUE
    if [ "$CONTINUE" != "yes" ]; then
        exit 1
    fi
fi

# Check if using HTTPS
if ! grep -q "BASE_URL=https://" .env.${ENVIRONMENT}; then
    echo -e "${RED}WARNING: BASE_URL is not using HTTPS!${NC}"
    echo "HTTPS is strongly recommended for production."
    read -p "Continue anyway? (not recommended) Type 'yes': " CONTINUE
    if [ "$CONTINUE" != "yes" ]; then
        exit 1
    fi
fi

# Docker registry authentication
echo ""
echo -e "${YELLOW}Logging in to Docker registry...${NC}"
if [ -n "$DOCKER_REGISTRY_USERNAME" ] && [ -n "$DOCKER_REGISTRY_PASSWORD" ]; then
    echo "$DOCKER_REGISTRY_PASSWORD" | docker login git.64b.de -u "$DOCKER_REGISTRY_USERNAME" --password-stdin
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to authenticate with Docker registry!${NC}"
        echo "Please set DOCKER_REGISTRY_USERNAME and DOCKER_REGISTRY_PASSWORD environment variables."
        exit 1
    fi
else
    echo -e "${RED}ERROR: Docker registry credentials required for production!${NC}"
    echo "Please set DOCKER_REGISTRY_USERNAME and DOCKER_REGISTRY_PASSWORD environment variables."
    exit 1
fi

# Create backup before deployment
echo ""
echo -e "${YELLOW}Creating pre-deployment backup...${NC}"
if docker compose -f "$COMPOSE_FILE" ps db-${ENVIRONMENT} | grep -q "Up"; then
    deployment/scripts/backup-db.sh ${ENVIRONMENT}
else
    echo "Database not running, skipping backup"
fi

# Pull latest images
echo ""
echo -e "${YELLOW}Pulling Docker image: git.64b.de/bjoern/deye_hard:${IMAGE_TAG}...${NC}"
docker compose -f "$COMPOSE_FILE" pull
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to pull Docker images!${NC}"
    echo "Check your registry authentication and network connectivity."
    echo "Aborting deployment."
    exit 1
fi

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker compose -f "$COMPOSE_FILE" up -d

# Wait for database to be ready
echo -e "${YELLOW}Waiting for database to be ready...${NC}"
sleep 30

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker compose -f "$COMPOSE_FILE" exec backend-${ENVIRONMENT} \
    sh -c "ENV_FILE=/app/.env uv run alembic upgrade head"

# Check service health
echo ""
echo -e "${YELLOW}Checking service health...${NC}"
docker compose -f "$COMPOSE_FILE" ps

# Test health endpoint
echo ""
echo -e "${YELLOW}Testing health endpoint...${NC}"
sleep 5
curl -f https://solar.64b.de/healthcheck || curl -f http://solar.64b.de/healthcheck || echo -e "${RED}Health check failed!${NC}"

# Create post-deployment backup
echo ""
echo -e "${YELLOW}Creating post-deployment backup...${NC}"
deployment/scripts/backup-db.sh ${ENVIRONMENT}

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  PRODUCTION DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Image deployed: git.64b.de/bjoern/deye_hard:${IMAGE_TAG}"
echo ""
echo "Services:"
echo "  - Backend: https://solar.64b.de"
echo "  - API Docs: https://solar.64b.de/docs"
echo "  - Admin: https://solar.64b.de/admin"
echo ""
echo "Monitoring:"
echo "  - Check SignOz dashboard for any errors"
echo "  - Monitor logs: docker compose -f $COMPOSE_FILE logs -f"
echo "  - Check alerts: Review email for any alert notifications"
echo ""
echo "Rollback (if needed):"
echo "  - Restore backup: deployment/scripts/restore-db.sh ${ENVIRONMENT} [backup_file]"
echo "  - Deploy previous version: IMAGE_TAG=<previous-tag> deployment/scripts/deploy-prod.sh"
echo ""
echo -e "${YELLOW}Post-deployment checklist:${NC}"
echo "  [ ] Test user login"
echo "  [ ] Test data collection (check inverter data arriving)"
echo "  [ ] Check SignOz for errors"
echo "  [ ] Verify email sending (password reset)"
echo "  [ ] Test API endpoints"
echo "  [ ] Monitor for 30 minutes"
echo ""
