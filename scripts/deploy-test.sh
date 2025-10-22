#!/bin/bash

# Test Environment Deployment Script
# Usage: ./deploy-test.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT="test"
COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Environment Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env.test exists
if [ ! -f ".env.${ENVIRONMENT}" ]; then
    echo -e "${RED}Error: .env.${ENVIRONMENT} not found!${NC}"
    echo "Please copy .env.${ENVIRONMENT}.example to .env.${ENVIRONMENT} and configure it."
    exit 1
fi

# Check if Traefik network exists
if ! docker network ls | grep -q "traefik-public"; then
    echo -e "${YELLOW}Creating traefik-public network...${NC}"
    docker network create traefik-public
fi

# Pull latest images
echo -e "${YELLOW}Pulling latest Docker images...${NC}"
docker compose -f "$COMPOSE_FILE" pull

# Build services
echo -e "${YELLOW}Building services...${NC}"
docker compose -f "$COMPOSE_FILE" build

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker compose -f "$COMPOSE_FILE" up -d

# Wait for database to be ready
echo -e "${YELLOW}Waiting for database to be ready...${NC}"
sleep 30

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
docker compose -f "$COMPOSE_FILE" exec backend-${ENVIRONMENT} \
    sh -c "ENV_FILE=/app/backend.env uv run alembic upgrade head"

# Check service health
echo ""
echo -e "${YELLOW}Checking service health...${NC}"
docker compose -f "$COMPOSE_FILE" ps

# Test health endpoint
echo ""
echo -e "${YELLOW}Testing health endpoint...${NC}"
sleep 5
curl -f http://test.yourdomain.com/healthcheck || echo -e "${RED}Health check failed!${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Services:"
echo "  - Backend: http://test.yourdomain.com"
echo "  - API Docs: http://test.yourdomain.com/docs"
echo "  - Admin: http://test.yourdomain.com/admin"
echo "  - SignOz: http://signoz.yourdomain.com/test"
echo ""
echo "Useful commands:"
echo "  - View logs: docker compose -f $COMPOSE_FILE logs -f"
echo "  - Check status: docker compose -f $COMPOSE_FILE ps"
echo "  - Restart service: docker compose -f $COMPOSE_FILE restart [service]"
echo "  - Stop all: docker compose -f $COMPOSE_FILE down"
echo ""
