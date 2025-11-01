#!/bin/bash

# Docker Image Build and Push Script
# Usage:
#   ./build-and-push.sh [TAG]
#   ./build-and-push.sh --env [test|staging|prod]
#   ./build-and-push.sh v1.2.3

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REGISTRY="git.64b.de"
IMAGE_NAME="bjoern/deye_hard"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}"

# Default to latest if no tag specified
TAG="${1:-latest}"

# Parse arguments
if [ "$1" == "--env" ]; then
    if [ -z "$2" ]; then
        echo -e "${RED}Error: --env requires an environment argument${NC}"
        echo "Usage: $0 --env [test|staging|prod]"
        exit 1
    fi
    TAG="$2"
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Docker Image Build and Push${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}Registry: ${REGISTRY}${NC}"
echo -e "${BLUE}Image: ${IMAGE_NAME}${NC}"
echo -e "${BLUE}Tag: ${TAG}${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running!${NC}"
    exit 1
fi

# Get git commit SHA for tagging
GIT_SHA=$(git rev-parse --short HEAD)
echo -e "${YELLOW}Git commit: ${GIT_SHA}${NC}"
echo ""

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}Warning: You have uncommitted changes!${NC}"
    read -p "Continue anyway? (y/N): " CONTINUE
    if [ "$CONTINUE" != "y" ] && [ "$CONTINUE" != "Y" ]; then
        echo "Build cancelled"
        exit 0
    fi
fi

# Docker registry authentication
echo -e "${YELLOW}Logging in to Docker registry...${NC}"
if [ -n "$DOCKER_REGISTRY_USERNAME" ] && [ -n "$DOCKER_REGISTRY_PASSWORD" ]; then
    echo "$DOCKER_REGISTRY_PASSWORD" | docker login ${REGISTRY} -u "$DOCKER_REGISTRY_USERNAME" --password-stdin
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to authenticate with Docker registry!${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Docker registry credentials not found in environment.${NC}"
    echo "Attempting interactive login..."
    docker login ${REGISTRY}
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to authenticate with Docker registry!${NC}"
        exit 1
    fi
fi

# Build the image
echo ""
echo -e "${YELLOW}Building Docker image...${NC}"
docker build \
    --tag ${FULL_IMAGE}:${TAG} \
    --tag ${FULL_IMAGE}:sha-${GIT_SHA} \
    --label "org.opencontainers.image.title=Deye Hard Backend" \
    --label "org.opencontainers.image.description=FastAPI-based solar inverter management system" \
    --label "org.opencontainers.image.version=${TAG}" \
    --label "org.opencontainers.image.created=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
    --label "org.opencontainers.image.source=$(git config --get remote.origin.url)" \
    .

if [ $? -ne 0 ]; then
    echo -e "${RED}Docker build failed!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Build successful!${NC}"
echo ""
echo "Built images:"
echo "  - ${FULL_IMAGE}:${TAG}"
echo "  - ${FULL_IMAGE}:sha-${GIT_SHA}"
echo ""

# Ask for confirmation before pushing
read -p "Push images to registry? (y/N): " PUSH_CONFIRM
if [ "$PUSH_CONFIRM" != "y" ] && [ "$PUSH_CONFIRM" != "Y" ]; then
    echo "Push cancelled. Images are available locally."
    exit 0
fi

# Push the images
echo ""
echo -e "${YELLOW}Pushing images to registry...${NC}"
docker push ${FULL_IMAGE}:${TAG}
docker push ${FULL_IMAGE}:sha-${GIT_SHA}

if [ $? -ne 0 ]; then
    echo -e "${RED}Docker push failed!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Push Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Images pushed:"
echo "  - ${FULL_IMAGE}:${TAG}"
echo "  - ${FULL_IMAGE}:sha-${GIT_SHA}"
echo ""
echo "Pull command:"
echo "  docker pull ${FULL_IMAGE}:${TAG}"
echo ""
echo "Deploy to environment:"
echo "  export IMAGE_TAG=${TAG}"
echo "  deployment/scripts/deploy-test.sh      # For test environment"
echo "  deployment/scripts/deploy-staging.sh   # For staging environment"
echo "  deployment/scripts/deploy-prod.sh      # For production environment"
echo ""
