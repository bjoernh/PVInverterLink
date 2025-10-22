# Deye Hard Backend - Production Deployment Guide

> Complete guide for deploying the solar inverter management system on Ubuntu with Docker, Traefik, and SignOz monitoring

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Server Setup](#server-setup)
5. [Testing Environment](#testing-environment)
6. [Staging Environment](#staging-environment)
7. [Production Environment](#production-environment)
8. [Database Migration (Optional)](#database-migration-optional)
9. [Monitoring Setup](#monitoring-setup)
10. [SSL/TLS Configuration](#ssltls-configuration)
11. [Backup Strategy](#backup-strategy)
12. [Troubleshooting](#troubleshooting)
13. [Maintenance](#maintenance)

---

## Overview

This guide covers deploying a three-tier architecture:

- **Testing**: `test.yourdomain.com` - For experimental features and testing
- **Staging**: `staging.yourdomain.com` - Pre-production verification
- **Production**: `yourdomain.com` - Live production system

All environments include full observability with SignOz monitoring from day one.

### What Gets Deployed

- ✅ FastAPI backend with HTMX web UI
- ✅ TimescaleDB (PostgreSQL + time-series extension)
- ✅ Rust collector for Deye inverters
- ✅ SignOz monitoring stack (OpenTelemetry)
- ✅ Traefik reverse proxy
- ✅ PostgreSQL metrics exporter
- ✅ Automated backups

---

## Architecture

```
Internet
    ↓
Traefik Reverse Proxy (Port 80/443)
    ├── test.yourdomain.com → Test Environment
    ├── staging.yourdomain.com → Staging Environment
    ├── yourdomain.com → Production Environment
    └── signoz.yourdomain.com → Monitoring Dashboard

Each Environment Contains:
├── FastAPI Backend (Port 8000)
├── TimescaleDB (Port 5432)
├── Rust Collector (Port 10000)
├── SignOz Stack
│   ├── OTEL Collector (Port 4317)
│   ├── Query Service (Port 8080)
│   └── Frontend (Port 3301)
└── PostgreSQL Exporter (Port 9187)
```

---

## Prerequisites

### 1. Server Requirements

**Minimum Hardware:**
- 4 CPU cores
- 8 GB RAM
- 100 GB SSD storage
- Ubuntu 22.04 LTS or newer

**Recommended Hardware:**
- 8 CPU cores
- 16 GB RAM
- 250 GB SSD storage

### 2. Domain Setup

Configure DNS A records pointing to your server IP:

```
test.yourdomain.com      → YOUR_SERVER_IP
staging.yourdomain.com   → YOUR_SERVER_IP
yourdomain.com           → YOUR_SERVER_IP
signoz.yourdomain.com    → YOUR_SERVER_IP
```

**Verification:**
```bash
dig test.yourdomain.com +short
# Should return your server IP
```

### 3. Software Requirements

- Docker Engine 24.0+
- Docker Compose v2.20+
- Git

---

## Server Setup

### Step 1: Initial Server Configuration

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y curl git ufw fail2ban

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp     # HTTP
sudo ufw allow 443/tcp    # HTTPS
sudo ufw allow 10000/tcp  # Solarman collector
sudo ufw enable

# Install fail2ban for SSH protection
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Step 2: Install Docker

```bash
# Remove old versions
sudo apt remove docker docker-engine docker.io containerd runc

# Install Docker using official script
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add current user to docker group
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
exit
```

**Log back in and verify Docker:**
```bash
docker --version
docker compose version
```

### Step 3: Clone Repository

```bash
# Create application directory
mkdir -p ~/solar-backend
cd ~/solar-backend

# Clone repository
git clone --recursive https://github.com/yourusername/solar-backend.git .

# Verify submodules (Rust collector)
git submodule update --init --recursive
```

### Step 4: Create Directory Structure

```bash
# Create directories for persistent data
mkdir -p data/{test,staging,prod}/{postgres,signoz,backups}
mkdir -p logs/{test,staging,prod}
mkdir -p traefik/{dynamic,certs}

# Set permissions
chmod 700 data
chmod 700 logs
```

---

## Testing Environment

The testing environment is deployed first to verify everything works.

### Step 1: Configure Environment

```bash
# Copy example environment file
cp .env.test.example .env.test

# Edit configuration
nano .env.test
```

**Required settings in `.env.test`:**

```bash
# Database
DATABASE_URL=postgresql+asyncpg://deyehard:CHANGE_THIS_PASSWORD@db-test:5432/deyehard
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD

# Security (generate strong random values)
AUTH_SECRET=GENERATE_32_CHAR_RANDOM_STRING
ENCRYPTION_KEY=GENERATE_FERNET_KEY_BASE64

# Application
BASE_URL=http://test.yourdomain.com
COOKIE_SECURE=False  # True when SSL enabled

# Timezone
TZ=Europe/Berlin

# Email (optional for testing)
FASTMAIL__SUPPRESS_SEND=true
FASTMAIL__MAIL_FROM=noreply@yourdomain.com

# Monitoring
OTEL_EXPORTER_OTLP_ENDPOINT=http://signoz-otel-collector-test:4317
OTEL_SERVICE_NAME=solar-backend-test

# Collector
COLLECTOR_PORT=10000
COLLECTOR_BACKEND_URL=http://backend-test:80
```

**Generate secure secrets:**

```bash
# Generate AUTH_SECRET (32+ characters)
openssl rand -hex 32

# Generate ENCRYPTION_KEY (Fernet key)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Step 2: Deploy Testing Stack

```bash
# Pull Docker images
docker compose -f docker-compose.test.yml pull

# Start services
docker compose -f docker-compose.test.yml up -d

# Wait for database to be ready (30 seconds)
sleep 30

# Verify all containers are running
docker compose -f docker-compose.test.yml ps
```

**Expected output:**
```
NAME                          STATUS
traefik                       Up
backend-test                  Up (healthy)
db-test                       Up (healthy)
collector-test                Up
signoz-otel-collector-test    Up
signoz-query-service-test     Up
signoz-frontend-test          Up
postgres-exporter-test        Up
```

### Step 3: Run Database Migrations

```bash
# Run migrations
docker compose -f docker-compose.test.yml exec backend-test \
  sh -c "ENV_FILE=/app/backend.env uv run alembic upgrade head"

# Verify migration success
docker compose -f docker-compose.test.yml exec backend-test \
  sh -c "ENV_FILE=/app/backend.env uv run alembic current"
```

### Step 4: Create Admin User

```bash
# Access backend container
docker compose -f docker-compose.test.yml exec backend-test sh

# Inside container, create superuser (interactive Python)
ENV_FILE=/app/backend.env uv run python

# Python console:
from solar_backend.db import async_session_maker, User
from solar_backend.users import get_user_manager
from fastapi_users.password import PasswordHelper
import asyncio

async def create_admin():
    async with async_session_maker() as session:
        # Check if admin exists
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == "admin@yourdomain.com"))
        if result.scalar_one_or_none():
            print("Admin user already exists")
            return

        # Create admin user
        password_helper = PasswordHelper()
        hashed = password_helper.hash("CHANGE_THIS_PASSWORD")

        admin = User(
            email="admin@yourdomain.com",
            hashed_password=hashed,
            is_active=True,
            is_superuser=True,
            is_verified=True
        )
        session.add(admin)
        await session.commit()
        print("Admin user created successfully")

asyncio.run(create_admin())
exit()

# Exit container
exit
```

### Step 5: Verify Testing Environment

```bash
# Test backend health
curl http://test.yourdomain.com/healthcheck
# Expected: {"status": "healthy"}

# Test admin interface
curl -I http://test.yourdomain.com/admin
# Expected: HTTP 200 OK (redirect to login)

# Test API documentation
curl -I http://test.yourdomain.com/docs
# Expected: HTTP 200 OK

# Test SignOz UI
curl -I http://signoz.yourdomain.com
# Expected: HTTP 200 OK

# View logs
docker compose -f docker-compose.test.yml logs -f backend-test
```

### Step 6: Test Data Collection

**For Deye inverters:**

```bash
# Check collector is listening
docker compose -f docker-compose.test.yml exec collector-test netstat -tlnp | grep 10000
# Expected: tcp 0.0.0.0:10000 LISTEN

# Configure Solarman logger to point to:
# Server IP: YOUR_SERVER_IP
# Port: 10000

# Monitor collector logs
docker compose -f docker-compose.test.yml logs -f collector-test
```

**For OpenDTU devices:**

```bash
# Test measurement endpoint
curl -X POST http://test.yourdomain.com/api/opendtu/measurements \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2025-10-22T12:00:00+02:00",
    "dtu_serial": "test-dtu-001",
    "inverters": [{
      "serial": "test-inverter-001",
      "name": "Test Inverter",
      "reachable": true,
      "producing": true,
      "last_update": 1729594800,
      "measurements": {
        "power_ac": 100.5,
        "voltage_ac": 230.0,
        "current_ac": 0.44,
        "frequency": 50.0,
        "power_factor": 1.0,
        "power_dc": 105.0
      }
    }]
  }'
```

---

## Staging Environment

Deploy staging after testing environment is verified and stable.

### Step 1: Configure Staging

```bash
# Copy and configure staging environment
cp .env.test.example .env.staging
nano .env.staging
```

**Update these values in `.env.staging`:**

```bash
DATABASE_URL=postgresql+asyncpg://deyehard:DIFFERENT_PASSWORD@db-staging:5432/deyehard
POSTGRES_PASSWORD=DIFFERENT_PASSWORD
AUTH_SECRET=DIFFERENT_32_CHAR_RANDOM_STRING
ENCRYPTION_KEY=DIFFERENT_FERNET_KEY
BASE_URL=http://staging.yourdomain.com
OTEL_SERVICE_NAME=solar-backend-staging
```

### Step 2: Deploy Staging

```bash
# Deploy staging stack
docker compose -f docker-compose.staging.yml up -d

# Wait for database
sleep 30

# Run migrations
docker compose -f docker-compose.staging.yml exec backend-staging \
  sh -c "ENV_FILE=/app/backend.env uv run alembic upgrade head"

# Create admin user (same process as test environment)
# Verify health
curl http://staging.yourdomain.com/healthcheck
```

### Step 3: Import Test Data (Optional)

```bash
# Export from test environment
docker compose -f docker-compose.test.yml exec db-test \
  pg_dump -U deyehard deyehard > staging_import.sql

# Import to staging
docker compose -f docker-compose.staging.yml exec -T db-staging \
  psql -U deyehard deyehard < staging_import.sql
```

---

## Production Environment

Deploy production only after staging is thoroughly tested.

### Step 1: Configure Production

```bash
# Copy and configure production environment
cp .env.staging.example .env.prod
nano .env.prod
```

**Production-specific settings in `.env.prod`:**

```bash
DATABASE_URL=postgresql+asyncpg://deyehard:STRONG_PROD_PASSWORD@db-prod:5432/deyehard
POSTGRES_PASSWORD=STRONG_PROD_PASSWORD
AUTH_SECRET=STRONG_PROD_SECRET_32_CHARS
ENCRYPTION_KEY=STRONG_PROD_FERNET_KEY
BASE_URL=https://yourdomain.com  # Note: HTTPS
COOKIE_SECURE=True  # Required for production
OTEL_SERVICE_NAME=solar-backend-production

# Email (required for production)
FASTMAIL__SUPPRESS_SEND=false
FASTMAIL__MAIL_USERNAME=smtp-user@yourdomain.com
FASTMAIL__MAIL_PASSWORD=your-smtp-password
FASTMAIL__MAIL_FROM=noreply@yourdomain.com
FASTMAIL__MAIL_SERVER=smtp.yourdomain.com
FASTMAIL__MAIL_PORT=587
FASTMAIL__MAIL_STARTTLS=true
FASTMAIL__MAIL_SSL_TLS=false
```

### Step 2: Deploy Production

```bash
# Deploy production stack
docker compose -f docker-compose.prod.yml up -d

# Wait for database
sleep 30

# Run migrations
docker compose -f docker-compose.prod.yml exec backend-prod \
  sh -c "ENV_FILE=/app/backend.env uv run alembic upgrade head"

# Create admin user
# Verify health
curl https://yourdomain.com/healthcheck
```

### Step 3: Production Health Check

```bash
# Check all services
docker compose -f docker-compose.prod.yml ps

# Check logs for errors
docker compose -f docker-compose.prod.yml logs --tail=100

# Verify database connectivity
docker compose -f docker-compose.prod.yml exec backend-prod \
  sh -c "ENV_FILE=/app/backend.env uv run python -c 'from solar_backend.db import engine; import asyncio; asyncio.run(engine.dispose())'"

# Test API endpoints
curl https://yourdomain.com/docs
curl https://yourdomain.com/admin
```

---

## Database Migration (Optional)

### Export from Development Database

If you have existing data in your development environment that you want to migrate:

```bash
# On your development machine
cd /path/to/solar-backend

# Export database
docker compose exec db pg_dump -U deyehard -Fc deyehard > dev_export.dump

# Or export as SQL
docker compose exec db pg_dump -U deyehard deyehard > dev_export.sql

# Copy to server
scp dev_export.dump user@YOUR_SERVER_IP:~/solar-backend/
```

### Import to Production

```bash
# On production server
cd ~/solar-backend

# For custom format (.dump)
docker compose -f docker-compose.prod.yml exec -T db-prod \
  pg_restore -U deyehard -d deyehard < dev_export.dump

# Or for SQL format
docker compose -f docker-compose.prod.yml exec -T db-prod \
  psql -U deyehard deyehard < dev_export.sql

# Verify data
docker compose -f docker-compose.prod.yml exec db-prod \
  psql -U deyehard -d deyehard -c "SELECT COUNT(*) FROM users;"
```

**Important:** Ensure you run migrations after import:

```bash
docker compose -f docker-compose.prod.yml exec backend-prod \
  sh -c "ENV_FILE=/app/backend.env uv run alembic upgrade head"
```

---

## Monitoring Setup

### Access SignOz Dashboard

```bash
# SignOz UI is available at:
http://signoz.yourdomain.com

# Default credentials (change immediately):
Username: admin@signoz.io
Password: admin
```

### Configure Email Alerts

1. **Access SignOz UI** → Settings → Notification Channels
2. **Add SMTP Channel:**
   - Name: `Production Alerts`
   - SMTP Host: `smtp.yourdomain.com`
   - SMTP Port: `587`
   - From: `monitoring@yourdomain.com`
   - Username: `smtp-user`
   - Password: `your-smtp-password`
   - TLS: `Enabled`

3. **Test Alert Delivery:**
   - Send test notification
   - Check spam folder if not received

### Create Alert Rules

**Critical Alerts (Tier 1):**

1. **Collector Down:**
   ```
   Metric: collector_messages_received_total
   Condition: rate[5m] == 0
   Duration: 10 minutes
   Severity: Critical
   Channel: Production Alerts
   ```

2. **High Error Rate:**
   ```
   Metric: http_server_errors_total
   Condition: rate[5m] > 0.10  # 10% error rate
   Duration: 5 minutes
   Severity: Critical
   Channel: Production Alerts
   ```

3. **Database Connections Exhausted:**
   ```
   Metric: postgres_connections_active
   Condition: > 90% of max_connections
   Duration: 5 minutes
   Severity: Critical
   Channel: Production Alerts
   ```

See `docs/MONITORING.md` for complete alert configuration.

### View Dashboards

Pre-configured dashboards are available:

- **Home Dashboard**: Overview of system health
- **FastAPI Dashboard**: API performance, error rates, latency
- **Collector Dashboard**: TCP connections, message processing, errors
- **PostgreSQL Dashboard**: Database health, query performance, storage

---

## SSL/TLS Configuration

### Enable Let's Encrypt (Future)

When ready to enable HTTPS with automatic SSL certificates:

```bash
# Edit traefik/traefik.yml
nano traefik/traefik.yml

# Uncomment the certificatesResolvers section:
certificatesResolvers:
  letsencrypt:
    acme:
      email: admin@yourdomain.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web

# Update dynamic routing to use HTTPS
nano traefik/dynamic/routers.yml

# Restart Traefik
docker compose -f docker-compose.prod.yml restart traefik

# Verify certificates
docker compose -f docker-compose.prod.yml logs traefik | grep -i acme
```

### Manual Certificate Installation

If using custom certificates:

```bash
# Copy certificates to server
scp yourdomain.com.crt user@YOUR_SERVER_IP:~/solar-backend/traefik/certs/
scp yourdomain.com.key user@YOUR_SERVER_IP:~/solar-backend/traefik/certs/

# Update Traefik configuration
nano traefik/dynamic/certificates.yml

# Add certificate configuration:
tls:
  certificates:
    - certFile: /certs/yourdomain.com.crt
      keyFile: /certs/yourdomain.com.key

# Restart Traefik
docker compose -f docker-compose.prod.yml restart traefik
```

---

## Backup Strategy

### Automated Daily Backups

```bash
# Make backup script executable
chmod +x scripts/backup-db.sh

# Test backup manually
./scripts/backup-db.sh prod

# Verify backup created
ls -lh data/prod/backups/

# Set up cron job for daily backups at 2 AM
crontab -e

# Add line:
0 2 * * * /home/youruser/solar-backend/scripts/backup-db.sh prod >> /home/youruser/solar-backend/logs/backup.log 2>&1
```

### Backup Retention Policy

The backup script automatically:
- Creates compressed SQL dumps
- Keeps last 7 daily backups
- Keeps last 4 weekly backups (Sunday)
- Keeps last 12 monthly backups (1st of month)

### Manual Backup

```bash
# Create manual backup
docker compose -f docker-compose.prod.yml exec db-prod \
  pg_dump -U deyehard -Fc deyehard > manual_backup_$(date +%Y%m%d).dump

# Restore from backup
docker compose -f docker-compose.prod.yml exec -T db-prod \
  pg_restore -U deyehard -d deyehard < manual_backup_20251022.dump
```

### Backup Verification

```bash
# Verify backup integrity
docker compose -f docker-compose.prod.yml exec db-prod \
  pg_restore --list manual_backup_20251022.dump

# Test restore in test environment
docker compose -f docker-compose.test.yml exec -T db-test \
  pg_restore -U deyehard -d deyehard < manual_backup_20251022.dump
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs backend-prod

# Check if port is in use
sudo netstat -tlnp | grep 8000

# Restart specific service
docker compose -f docker-compose.prod.yml restart backend-prod

# Rebuild container
docker compose -f docker-compose.prod.yml up -d --build backend-prod
```

### Database Connection Issues

```bash
# Verify database is running
docker compose -f docker-compose.prod.yml ps db-prod

# Check database logs
docker compose -f docker-compose.prod.yml logs db-prod

# Test connection
docker compose -f docker-compose.prod.yml exec db-prod \
  psql -U deyehard -d deyehard -c "SELECT version();"

# Reset database connections
docker compose -f docker-compose.prod.yml exec db-prod \
  psql -U deyehard -d deyehard -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'deyehard' AND pid <> pg_backend_pid();"
```

### Collector Not Receiving Data

```bash
# Check if collector is listening
docker compose -f docker-compose.prod.yml exec collector-prod netstat -tlnp

# Check firewall
sudo ufw status

# Test collector connectivity from external
telnet YOUR_SERVER_IP 10000

# Check collector logs
docker compose -f docker-compose.prod.yml logs -f collector-prod
```

### High Memory Usage

```bash
# Check container resource usage
docker stats

# Identify high-memory containers
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}" | sort -k 2 -h

# Restart high-memory service
docker compose -f docker-compose.prod.yml restart backend-prod

# Clear Docker cache (caution: removes unused images/containers)
docker system prune -a
```

### Traefik Routing Issues

```bash
# Check Traefik logs
docker logs traefik

# Verify routing configuration
docker exec traefik cat /etc/traefik/dynamic/routers.yml

# Access Traefik dashboard
curl http://YOUR_SERVER_IP:8080/dashboard/

# Test routing
curl -H "Host: yourdomain.com" http://YOUR_SERVER_IP/healthcheck
```

### SignOz Not Showing Data

```bash
# Check OTEL collector
docker compose -f docker-compose.prod.yml logs signoz-otel-collector-prod

# Verify backend is sending data
docker compose -f docker-compose.prod.yml logs backend-prod | grep -i otel

# Check network connectivity
docker compose -f docker-compose.prod.yml exec backend-prod \
  nc -zv signoz-otel-collector-prod 4317

# Restart SignOz stack
docker compose -f docker-compose.prod.yml restart signoz-otel-collector-prod signoz-query-service-prod signoz-frontend-prod
```

---

## Maintenance

### Regular Tasks

**Daily:**
- Check monitoring dashboard for alerts
- Review error logs: `docker compose -f docker-compose.prod.yml logs --tail=100 | grep ERROR`
- Verify backups completed: `ls -lh data/prod/backups/`

**Weekly:**
- Review resource usage: `docker stats --no-stream`
- Check disk space: `df -h`
- Review slow queries in SignOz
- Update dependencies if security patches available

**Monthly:**
- Review and rotate API keys
- Analyze performance trends
- Test backup restore procedure
- Review user access and permissions

### Update Procedure

```bash
# Pull latest code
cd ~/solar-backend
git pull origin main
git submodule update --recursive

# Review changes
git log --oneline -10

# Test in staging first
docker compose -f docker-compose.staging.yml pull
docker compose -f docker-compose.staging.yml up -d --build

# Run migrations (staging)
docker compose -f docker-compose.staging.yml exec backend-staging \
  sh -c "ENV_FILE=/app/backend.env uv run alembic upgrade head"

# Verify staging works
curl http://staging.yourdomain.com/healthcheck

# Deploy to production
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations (production)
docker compose -f docker-compose.prod.yml exec backend-prod \
  sh -c "ENV_FILE=/app/backend.env uv run alembic upgrade head"

# Verify production
curl https://yourdomain.com/healthcheck
```

### Rollback Procedure

```bash
# Identify last working version
git log --oneline -10

# Checkout previous version
git checkout <commit-hash>
git submodule update --recursive

# Rebuild and deploy
docker compose -f docker-compose.prod.yml up -d --build

# Rollback database if needed
docker compose -f docker-compose.prod.yml exec backend-prod \
  sh -c "ENV_FILE=/app/backend.env uv run alembic downgrade -1"
```

### Log Rotation

```bash
# Configure Docker log rotation
sudo nano /etc/docker/daemon.json

# Add:
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}

# Restart Docker
sudo systemctl restart docker

# Restart containers
docker compose -f docker-compose.prod.yml restart
```

---

## Security Checklist

Before going live:

- [ ] All passwords changed from defaults
- [ ] `COOKIE_SECURE=True` in production
- [ ] Firewall configured and enabled
- [ ] SSH key-based authentication (disable password auth)
- [ ] fail2ban configured and running
- [ ] Docker containers run as non-root users
- [ ] Environment files have restricted permissions (600)
- [ ] SSL/TLS certificates configured
- [ ] Admin interface restricted (IP whitelist or VPN)
- [ ] Backup encryption enabled
- [ ] Monitoring alerts configured
- [ ] Log rotation configured
- [ ] Security updates automated

---

## Support & Documentation

- **Main README**: `README.md` - Application overview
- **Development Guide**: `CLAUDE.md` - Development workflows
- **Monitoring Architecture**: `docs/MONITORING.md` - Observability setup
- **Collector Documentation**: `collector/README.md` - Rust collector details
- **API Documentation**: `https://yourdomain.com/docs` - Interactive API docs

---

## Quick Reference

### Environment URLs

| Environment | Backend | Monitoring | Admin |
|-------------|---------|------------|-------|
| Test | http://test.yourdomain.com | http://signoz.yourdomain.com (test namespace) | http://test.yourdomain.com/admin |
| Staging | http://staging.yourdomain.com | http://signoz.yourdomain.com (staging namespace) | http://staging.yourdomain.com/admin |
| Production | https://yourdomain.com | http://signoz.yourdomain.com (prod namespace) | https://yourdomain.com/admin |

### Common Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f [service-name]

# Restart service
docker compose -f docker-compose.prod.yml restart [service-name]

# Scale service
docker compose -f docker-compose.prod.yml up -d --scale backend-prod=3

# Execute command in container
docker compose -f docker-compose.prod.yml exec backend-prod sh

# Check resource usage
docker stats

# Backup database
./scripts/backup-db.sh prod

# Health check
curl https://yourdomain.com/healthcheck
```

---

**Deployment Guide Version:** 1.0
**Last Updated:** October 2025
**Maintainer:** WTF Kooperative eG
