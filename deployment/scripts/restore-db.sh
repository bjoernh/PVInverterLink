#!/bin/bash

# Database Restore Script
# Usage: ./restore-db.sh [environment] [backup_file]
# Example: ./restore-db.sh prod data/prod/backups/daily/backup_prod_daily_20251022_020000.sql.gz

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}Error: Missing arguments${NC}"
    echo "Usage: $0 [environment] [backup_file]"
    echo "Example: $0 prod data/prod/backups/daily/backup_prod_daily_20251022_020000.sql.gz"
    exit 1
fi

ENVIRONMENT=$1
BACKUP_FILE=$2
COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(test|staging|prod)$ ]]; then
    echo -e "${RED}Error: Invalid environment. Use: test, staging, or prod${NC}"
    exit 1
fi

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Error: Docker compose file not found: $COMPOSE_FILE${NC}"
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

# Verify backup file integrity
echo "Verifying backup file integrity..."
if ! gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo -e "${RED}Error: Backup file is corrupted!${NC}"
    exit 1
fi
echo -e "${GREEN}Backup file integrity verified${NC}"

# Warning for production
if [ "$ENVIRONMENT" = "prod" ]; then
    echo -e "${RED}WARNING: You are about to restore the PRODUCTION database!${NC}"
    echo -e "${RED}This will overwrite all current data.${NC}"
    echo ""
    read -p "Are you sure you want to continue? Type 'yes' to proceed: " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Restore cancelled"
        exit 0
    fi
fi

echo -e "${YELLOW}Starting database restore for ${ENVIRONMENT} environment...${NC}"
echo "Backup file: $BACKUP_FILE"

# Create a pre-restore backup
PRE_RESTORE_BACKUP="data/${ENVIRONMENT}/backups/pre-restore_$(date +%Y%m%d_%H%M%S).sql.gz"
echo "Creating pre-restore backup: $PRE_RESTORE_BACKUP"
docker compose -f "$COMPOSE_FILE" exec -T db-${ENVIRONMENT} \
    pg_dump -U deyehard deyehard | gzip > "$PRE_RESTORE_BACKUP"
echo -e "${GREEN}Pre-restore backup created${NC}"

# Stop backend service to prevent database access during restore
echo "Stopping backend service..."
docker compose -f "$COMPOSE_FILE" stop backend-${ENVIRONMENT}

# Terminate existing connections
echo "Terminating existing database connections..."
docker compose -f "$COMPOSE_FILE" exec db-${ENVIRONMENT} \
    psql -U deyehard -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'deyehard' AND pid <> pg_backend_pid();" || true

# Drop and recreate database
echo "Dropping and recreating database..."
docker compose -f "$COMPOSE_FILE" exec db-${ENVIRONMENT} \
    psql -U deyehard -d postgres -c "DROP DATABASE IF EXISTS deyehard;"
docker compose -f "$COMPOSE_FILE" exec db-${ENVIRONMENT} \
    psql -U deyehard -d postgres -c "CREATE DATABASE deyehard OWNER deyehard;"

# Enable TimescaleDB extension
echo "Enabling TimescaleDB extension..."
docker compose -f "$COMPOSE_FILE" exec db-${ENVIRONMENT} \
    psql -U deyehard -d deyehard -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Restore database
echo "Restoring database from backup..."
gunzip -c "$BACKUP_FILE" | docker compose -f "$COMPOSE_FILE" exec -T db-${ENVIRONMENT} \
    psql -U deyehard deyehard

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Database restored successfully!${NC}"
else
    echo -e "${RED}Database restore failed!${NC}"
    echo "Attempting to restore pre-restore backup..."
    gunzip -c "$PRE_RESTORE_BACKUP" | docker compose -f "$COMPOSE_FILE" exec -T db-${ENVIRONMENT} \
        psql -U deyehard deyehard
    echo -e "${YELLOW}Rolled back to pre-restore state${NC}"
    exit 1
fi

# Start backend service
echo "Starting backend service..."
docker compose -f "$COMPOSE_FILE" start backend-${ENVIRONMENT}

# Wait for backend to be healthy
echo "Waiting for backend to become healthy..."
sleep 10

# Verify backend is running
if docker compose -f "$COMPOSE_FILE" ps backend-${ENVIRONMENT} | grep -q "Up"; then
    echo -e "${GREEN}Backend service started successfully${NC}"
else
    echo -e "${RED}Warning: Backend service may not have started properly${NC}"
    echo "Check logs: docker compose -f $COMPOSE_FILE logs backend-${ENVIRONMENT}"
fi

# Summary
echo ""
echo "====== Restore Summary ======"
echo "Environment: ${ENVIRONMENT}"
echo "Backup file: ${BACKUP_FILE}"
echo "Pre-restore backup: ${PRE_RESTORE_BACKUP}"
echo ""
echo -e "${GREEN}Restore completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "1. Verify application is working: docker compose -f $COMPOSE_FILE ps"
echo "2. Check backend logs: docker compose -f $COMPOSE_FILE logs -f backend-${ENVIRONMENT}"
echo "3. Test application: curl http://$([ "$ENVIRONMENT" = "prod" ] && echo "yourdomain.com" || echo "${ENVIRONMENT}.yourdomain.com")/healthcheck"
