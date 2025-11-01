#!/bin/bash

# Staging Environment Deployment Script
# Usage: ./deploy-staging.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT="staging"
COMPOSE_FILE="deployment/docker-compose.${ENVIRONMENT}.yml"
# Default to 'staging' tag, or use environment variable
export IMAGE_TAG="${IMAGE_TAG:-staging}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Staging Environment Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}Image Tag: ${IMAGE_TAG}${NC}"
echo ""

# Check if .env.staging exists
if [ ! -f ".env.${ENVIRONMENT}" ]; then
    echo -e "${RED}Error: .env.${ENVIRONMENT} not found!${NC}"
    echo "Please copy .env.${ENVIRONMENT}.example to .env.${ENVIRONMENT} and configure it."
    exit 1
fi

# Docker registry authentication
echo -e "${YELLOW}Logging in to Docker registry...${NC}"
if [ -n "$DOCKER_REGISTRY_USERNAME" ] && [ -n "$DOCKER_REGISTRY_PASSWORD" ]; then
    echo "$DOCKER_REGISTRY_PASSWORD" | docker login git.64b.de -u "$DOCKER_REGISTRY_USERNAME" --password-stdin
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to authenticate with Docker registry!${NC}"
        echo "Please set DOCKER_REGISTRY_USERNAME and DOCKER_REGISTRY_PASSWORD environment variables."
        exit 1
    fi
else
    echo -e "${YELLOW}Warning: Docker registry credentials not provided.${NC}"
    echo "Set DOCKER_REGISTRY_USERNAME and DOCKER_REGISTRY_PASSWORD for automatic login."
    echo "Attempting to pull without authentication..."
fi

# Pull latest images
echo -e "${YELLOW}Pulling Docker image: git.64b.de/bjoern/deye_hard:${IMAGE_TAG}...${NC}"
docker compose -f "$COMPOSE_FILE" pull
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to pull Docker images!${NC}"
    echo "Check your registry authentication and network connectivity."
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
curl -f http://staging.solar.64b.de/healthcheck || echo -e "${RED}Health check failed!${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Image deployed: git.64b.de/bjoern/deye_hard:${IMAGE_TAG}"
echo ""
echo "Services:"
echo "  - Backend: http://staging.solar.64b.de"
echo "  - API Docs: http://staging.solar.64b.de/docs"
echo "  - Admin: http://staging.solar.64b.de/admin"
echo ""
echo "Useful commands:"
echo "  - View logs: docker compose -f $COMPOSE_FILE logs -f"
echo "  - Check status: docker compose -f $COMPOSE_FILE ps"
echo "  - Restart service: docker compose -f $COMPOSE_FILE restart [service]"
echo "  - Stop all: docker compose -f $COMPOSE_FILE down"
echo ""
