#!/bin/bash

# Database Backup Script
# Usage: ./backup-db.sh [environment]
# Example: ./backup-db.sh prod

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-prod}
BACKUP_DIR="data/${ENVIRONMENT}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y%m%d)
DAY_OF_WEEK=$(date +%u)  # 1-7 (Monday-Sunday)
DAY_OF_MONTH=$(date +%d)

# Compose file selection
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

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly}

echo -e "${GREEN}Starting database backup for ${ENVIRONMENT} environment...${NC}"

# Determine backup type and location
if [ "$DAY_OF_MONTH" = "01" ]; then
    BACKUP_TYPE="monthly"
    BACKUP_SUBDIR="monthly"
    RETENTION_DAYS=365  # Keep monthly backups for 1 year
elif [ "$DAY_OF_WEEK" = "7" ]; then  # Sunday
    BACKUP_TYPE="weekly"
    BACKUP_SUBDIR="weekly"
    RETENTION_DAYS=28  # Keep weekly backups for 4 weeks
else
    BACKUP_TYPE="daily"
    BACKUP_SUBDIR="daily"
    RETENTION_DAYS=7  # Keep daily backups for 7 days
fi

BACKUP_FILE="${BACKUP_DIR}/${BACKUP_SUBDIR}/backup_${ENVIRONMENT}_${BACKUP_TYPE}_${TIMESTAMP}.sql.gz"

echo -e "${YELLOW}Backup type: ${BACKUP_TYPE}${NC}"
echo -e "${YELLOW}Backup file: ${BACKUP_FILE}${NC}"

# Perform backup
echo "Creating database dump..."
docker compose -f "$COMPOSE_FILE" exec -T db-${ENVIRONMENT} \
    pg_dump -U deyehard deyehard | gzip > "$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}Backup completed successfully!${NC}"
    echo -e "${GREEN}Size: ${BACKUP_SIZE}${NC}"
    echo -e "${GREEN}Location: ${BACKUP_FILE}${NC}"
else
    echo -e "${RED}Backup failed!${NC}"
    exit 1
fi

# Verify backup integrity
echo "Verifying backup integrity..."
if gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo -e "${GREEN}Backup integrity verified${NC}"
else
    echo -e "${RED}Backup integrity check failed!${NC}"
    exit 1
fi

# Clean up old backups based on retention policy
echo "Cleaning up old backups..."

# Clean daily backups older than retention period
find "${BACKUP_DIR}/daily" -name "backup_${ENVIRONMENT}_daily_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete

# Clean weekly backups older than 4 weeks
find "${BACKUP_DIR}/weekly" -name "backup_${ENVIRONMENT}_weekly_*.sql.gz" -type f -mtime +28 -delete

# Clean monthly backups older than 12 months
find "${BACKUP_DIR}/monthly" -name "backup_${ENVIRONMENT}_monthly_*.sql.gz" -type f -mtime +365 -delete

echo -e "${GREEN}Old backups cleaned up${NC}"

# Summary
echo ""
echo "====== Backup Summary ======"
echo "Environment: ${ENVIRONMENT}"
echo "Type: ${BACKUP_TYPE}"
echo "File: ${BACKUP_FILE}"
echo "Size: ${BACKUP_SIZE}"
echo "Timestamp: ${TIMESTAMP}"
echo ""
echo "Retention Policy:"
echo "  - Daily: ${RETENTION_DAYS} days"
echo "  - Weekly: 4 weeks"
echo "  - Monthly: 12 months"
echo ""

# List current backups
echo "Current backups:"
echo "Daily backups:"
ls -lh "${BACKUP_DIR}/daily" 2>/dev/null | tail -n +2 || echo "  No daily backups"
echo ""
echo "Weekly backups:"
ls -lh "${BACKUP_DIR}/weekly" 2>/dev/null | tail -n +2 || echo "  No weekly backups"
echo ""
echo "Monthly backups:"
ls -lh "${BACKUP_DIR}/monthly" 2>/dev/null | tail -n +2 || echo "  No monthly backups"

echo ""
echo -e "${GREEN}Backup completed successfully!${NC}"
