#!/bin/bash

# Development Database Export Script
# Usage: ./export-dev-db.sh [output_file]
# Example: ./export-dev-db.sh dev_export_20251022.sql

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default output file
OUTPUT_FILE=${1:-"dev_export_$(date +%Y%m%d_%H%M%S).sql"}
COMPOSE_FILE="docker-compose.yml"

echo -e "${YELLOW}Exporting development database...${NC}"
echo "Output file: $OUTPUT_FILE"
echo ""

# Check if development containers are running
if ! docker compose -f "$COMPOSE_FILE" ps db | grep -q "Up"; then
    echo -e "${RED}Error: Development database container is not running!${NC}"
    echo "Start it with: docker compose up -d db"
    exit 1
fi

# Export database
echo "Creating database export..."
docker compose -f "$COMPOSE_FILE" exec -T db \
    pg_dump -U deyehard --clean --if-exists deyehard > "$OUTPUT_FILE"

if [ $? -eq 0 ]; then
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo -e "${GREEN}Export completed successfully!${NC}"
    echo "File: $OUTPUT_FILE"
    echo "Size: $FILE_SIZE"
    echo ""

    # Optionally create compressed version
    echo "Creating compressed version..."
    gzip -c "$OUTPUT_FILE" > "${OUTPUT_FILE}.gz"
    COMPRESSED_SIZE=$(du -h "${OUTPUT_FILE}.gz" | cut -f1)
    echo -e "${GREEN}Compressed file created: ${OUTPUT_FILE}.gz${NC}"
    echo "Compressed size: $COMPRESSED_SIZE"
    echo ""

    # Show summary
    echo "====== Export Summary ======"
    echo "SQL file: $OUTPUT_FILE ($FILE_SIZE)"
    echo "Compressed: ${OUTPUT_FILE}.gz ($COMPRESSED_SIZE)"
    echo ""
    echo "To import this export to a server:"
    echo "  1. Copy file to server:"
    echo "     scp ${OUTPUT_FILE}.gz user@server:~/solar-backend/"
    echo ""
    echo "  2. On server, import to target environment:"
    echo "     gunzip -c ${OUTPUT_FILE}.gz | docker compose -f docker-compose.prod.yml exec -T db-prod psql -U deyehard deyehard"
    echo ""
    echo "  3. Run migrations:"
    echo "     docker compose -f docker-compose.prod.yml exec backend-prod sh -c 'cd /app && ENV_FILE=/app/.env uv run alembic upgrade head'"
    echo ""
else
    echo -e "${RED}Export failed!${NC}"
    exit 1
fi
