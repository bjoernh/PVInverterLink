# Deployment Troubleshooting Guide

Common issues and solutions for the solar backend deployment.

## Table of Contents

1. [Container Issues](#container-issues)
2. [Network Issues](#network-issues)
3. [Database Issues](#database-issues)
4. [Traefik / Routing Issues](#traefik--routing-issues)
5. [Monitoring / SignOz Issues](#monitoring--signoz-issues)
6. [Data Collection Issues](#data-collection-issues)
7. [Performance Issues](#performance-issues)
8. [SSL/TLS Issues](#ssltls-issues)
9. [Backup / Restore Issues](#backup--restore-issues)
10. [Migration Issues](#migration-issues)

---

## Container Issues

### Container Won't Start

**Symptoms:**
- Container immediately exits after starting
- Container status shows "Exited (1)" or similar

**Diagnosis:**
```bash
# Check container logs
docker compose -f docker-compose.prod.yml logs backend-prod

# Check container status
docker compose -f docker-compose.prod.yml ps

# Inspect container
docker inspect backend-prod
```

**Common Causes & Solutions:**

1. **Port already in use:**
   ```bash
   # Find what's using the port
   sudo netstat -tlnp | grep 8000

   # Solution: Stop conflicting service or change port
   ```

2. **Environment file missing:**
   ```bash
   # Verify .env file exists
   ls -la .env.prod

   # Solution: Copy from example
   cp .env.prod.example .env.prod
   # Then configure with your values
   ```

3. **Database connection failure:**
   ```bash
   # Check if database is running
   docker compose -f docker-compose.prod.yml ps db-prod

   # Solution: Start database first
   docker compose -f docker-compose.prod.yml up -d db-prod
   ```

4. **Permission issues:**
   ```bash
   # Check file permissions
   ls -la backend.env

   # Solution: Fix permissions
   chmod 600 .env.prod
   ```

### Container Keeps Restarting

**Diagnosis:**
```bash
# Watch container status
watch -n 1 'docker compose -f docker-compose.prod.yml ps'

# Check logs for crash reason
docker compose -f docker-compose.prod.yml logs --tail=100 backend-prod
```

**Solutions:**

1. **Database not ready:**
   - Increase healthcheck wait time
   - Verify database container is healthy

2. **Configuration error:**
   - Check environment variables
   - Verify DATABASE_URL format

3. **Resource exhaustion:**
   - Check available memory: `free -h`
   - Increase container limits in docker-compose.yml

### High Memory Usage

**Diagnosis:**
```bash
# Check container memory usage
docker stats --no-stream

# Identify high-memory container
docker stats --format "table {{.Name}}\t{{.MemUsage}}" | sort -k 2 -h
```

**Solutions:**

1. **Backend high memory:**
   ```bash
   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend-prod

   # Check for memory leaks in logs
   docker logs backend-prod | grep -i "memory\|oom"
   ```

2. **Database high memory:**
   - This is normal for PostgreSQL (uses memory for caching)
   - Review `shared_buffers` setting in docker-compose.prod.yml
   - Consider increasing server RAM

3. **SignOz/ClickHouse high memory:**
   - Adjust retention policy (reduce data retention)
   - Increase resource limits if server has capacity

---

## Network Issues

### Can't Access Service from Browser

**Diagnosis:**
```bash
# Test from server
curl http://localhost:8000/healthcheck

# Test through Traefik
curl -H "Host: yourdomain.com" http://localhost/healthcheck

# Check if Traefik is routing correctly
docker logs traefik | grep yourdomain.com
```

**Solutions:**

1. **DNS not propagated:**
   ```bash
   # Check DNS resolution
   dig yourdomain.com +short

   # Wait for propagation (up to 48 hours)
   # Temporary solution: Add to /etc/hosts
   echo "YOUR_SERVER_IP yourdomain.com" | sudo tee -a /etc/hosts
   ```

2. **Firewall blocking:**
   ```bash
   # Check UFW status
   sudo ufw status

   # Allow ports
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

3. **Traefik not routing:**
   - Check Traefik dashboard: `http://YOUR_SERVER_IP:8080`
   - Verify labels in docker-compose.yml
   - Check Traefik logs

### "Connection Refused" Error

**Diagnosis:**
```bash
# Check if service is listening
sudo netstat -tlnp | grep :80

# Check if Traefik is running
docker ps | grep traefik
```

**Solutions:**

1. **Traefik not started:**
   ```bash
   docker compose -f docker-compose.test.yml up -d traefik
   ```

2. **Service not exposed:**
   - Verify `traefik.enable=true` label
   - Check network connectivity: `docker network inspect traefik-public`

### "502 Bad Gateway" Error

**Diagnosis:**
```bash
# Check backend health
docker compose -f docker-compose.prod.yml ps backend-prod

# Check backend logs
docker logs backend-prod --tail=50
```

**Solutions:**

1. **Backend not ready:**
   - Wait for healthcheck to pass
   - Increase startup timeout in Traefik config

2. **Backend crashed:**
   - Check logs for errors
   - Restart backend: `docker compose -f docker-compose.prod.yml restart backend-prod`

---

## Database Issues

### "Connection to database failed"

**Diagnosis:**
```bash
# Check database status
docker compose -f docker-compose.prod.yml ps db-prod

# Test connection manually
docker compose -f docker-compose.prod.yml exec db-prod \
  psql -U deyehard -d deyehard -c "SELECT version();"

# Check connection string
grep DATABASE_URL .env.prod
```

**Solutions:**

1. **Database not running:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d db-prod
   ```

2. **Wrong credentials:**
   - Verify `POSTGRES_PASSWORD` in .env.prod
   - Verify password in `DATABASE_URL`

3. **Database not initialized:**
   ```bash
   # Check database logs
   docker logs db-prod | grep -i error

   # Reinitialize if needed (WARNING: destroys data)
   docker compose -f docker-compose.prod.yml down -v
   docker compose -f docker-compose.prod.yml up -d db-prod
   ```

### Migration Failures

**Diagnosis:**
```bash
# Check migration status
docker compose -f docker-compose.prod.yml exec backend-prod \
  sh -c "ENV_FILE=/app/backend.env uv run alembic current"

# Check migration history
docker compose -f docker-compose.prod.yml exec backend-prod \
  sh -c "ENV_FILE=/app/backend.env uv run alembic history"
```

**Solutions:**

1. **Migration out of sync:**
   ```bash
   # Stamp current version
   docker compose -f docker-compose.prod.yml exec backend-prod \
     sh -c "ENV_FILE=/app/backend.env uv run alembic stamp head"
   ```

2. **Migration conflict:**
   - Restore from backup
   - Apply migrations manually
   - Check `alembic/versions/` for conflicts

### Slow Queries

**Diagnosis:**
```bash
# Check slow queries in SignOz dashboard
# Or query directly:
docker compose -f docker-compose.prod.yml exec db-prod \
  psql -U deyehard -d deyehard -c "
  SELECT query, calls, total_time, mean_time
  FROM pg_stat_statements
  ORDER BY mean_time DESC
  LIMIT 10;"
```

**Solutions:**

1. **Missing indexes:**
   - Review query plan: `EXPLAIN ANALYZE <query>`
   - Add appropriate indexes

2. **Too much data:**
   - Verify compression is working
   - Check retention policy

---

## Traefik / Routing Issues

### Traefik Dashboard Not Accessible

**Diagnosis:**
```bash
# Check if Traefik is running
docker ps | grep traefik

# Check Traefik logs
docker logs traefik --tail=50
```

**Solutions:**

1. **Dashboard disabled:**
   - Verify `api.insecure=true` in traefik.yml (dev only)
   - Or configure secure access with auth

2. **Port not exposed:**
   - Check `ports` in docker-compose.test.yml
   - Verify 8080 is exposed

### Routes Not Working

**Diagnosis:**
```bash
# Check Traefik routing config
docker exec traefik cat /etc/traefik/dynamic/routers.yml

# Test routing manually
curl -H "Host: test.yourdomain.com" http://localhost/healthcheck
```

**Solutions:**

1. **Wrong domain in labels:**
   - Verify `traefik.http.routers.*.rule` label
   - Check domain matches DNS

2. **Network issue:**
   ```bash
   # Check if backend is on traefik network
   docker network inspect traefik-public | grep backend-prod
   ```

3. **Label typo:**
   - Review all Traefik labels in docker-compose.yml
   - Look for typos in service names

---

## Monitoring / SignOz Issues

### SignOz UI Not Loading

**Diagnosis:**
```bash
# Check SignOz containers
docker ps | grep signoz

# Check frontend logs
docker logs signoz-frontend-prod

# Check query service
docker logs signoz-query-service-prod
```

**Solutions:**

1. **ClickHouse not running:**
   ```bash
   docker compose -f docker-compose.prod.yml ps clickhouse-prod
   docker compose -f docker-compose.prod.yml up -d clickhouse-prod
   ```

2. **Network issue:**
   - Verify SignOz services are on same network
   - Check `FRONTEND_API_ENDPOINT` env var

### No Traces Appearing

**Diagnosis:**
```bash
# Check OTEL collector
docker logs signoz-otel-collector-prod

# Verify backend is sending data
docker logs backend-prod | grep -i otel

# Test OTEL endpoint
docker compose -f docker-compose.prod.yml exec backend-prod \
  nc -zv signoz-otel-collector-prod 4317
```

**Solutions:**

1. **OTEL endpoint not configured:**
   - Verify `OTEL_EXPORTER_OTLP_ENDPOINT` in .env.prod
   - Should be `http://signoz-otel-collector-prod:4317`

2. **Instrumentation not enabled:**
   - Check OpenTelemetry libraries installed
   - Verify instrumentation code in backend

3. **Network connectivity:**
   - Ensure backend and collector on same Docker network

### Alerts Not Triggering

**Diagnosis:**
```bash
# Check alert configuration in SignOz UI
# Check SMTP logs
docker logs signoz-alertmanager-prod
```

**Solutions:**

1. **SMTP not configured:**
   - Verify SMTP settings in SignOz UI
   - Test email delivery

2. **Alert threshold not met:**
   - Verify metric values in dashboard
   - Adjust thresholds if needed

3. **Cooldown period:**
   - Check if alert is in cooldown
   - Wait for cooldown to expire

---

## Data Collection Issues

### Collector Not Receiving Data

**Diagnosis:**
```bash
# Check if collector is listening
docker compose -f docker-compose.prod.yml exec collector-prod \
  netstat -tlnp | grep 10000

# Check collector logs
docker logs collector-prod --tail=50

# Test port from external
telnet YOUR_SERVER_IP 10000
```

**Solutions:**

1. **Firewall blocking:**
   ```bash
   sudo ufw allow 10000/tcp
   ```

2. **Collector not started:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d collector-prod
   ```

3. **Wrong IP configured on inverter:**
   - Verify Solarman logger points to correct server IP
   - Verify port is 10000

### Data Not Appearing in Dashboard

**Diagnosis:**
```bash
# Check if measurements are being stored
docker compose -f docker-compose.prod.yml exec db-prod \
  psql -U deyehard -d deyehard -c "
  SELECT COUNT(*), MAX(time)
  FROM inverter_measurements;"

# Check collector logs for errors
docker logs collector-prod | grep -i error
```

**Solutions:**

1. **Authentication failing:**
   - Verify `API_KEY` matches in .env.prod and collector
   - Check collector logs for auth errors

2. **Database insert failing:**
   - Check database logs
   - Verify RLS policies are correct

3. **Inverter serial not registered:**
   - Add inverter in admin interface
   - Verify serial number matches

---

## Performance Issues

### High CPU Usage

**Diagnosis:**
```bash
# Check CPU usage per container
docker stats

# Check system CPU
top
```

**Solutions:**

1. **Backend high CPU:**
   - Check for infinite loops in code
   - Review slow API endpoints
   - Scale horizontally if needed

2. **Database high CPU:**
   - Analyze slow queries
   - Add indexes
   - Optimize query patterns

### High Disk Usage

**Diagnosis:**
```bash
# Check disk space
df -h

# Find large directories
du -h --max-depth=1 /var/lib/docker
du -h --max-depth=1 data/
```

**Solutions:**

1. **Old Docker images:**
   ```bash
   docker system prune -a
   ```

2. **Old backups:**
   - Review backup retention policy
   - Manually delete old backups

3. **Database too large:**
   - Verify compression is working
   - Adjust retention policy
   - Archive old data

---

## SSL/TLS Issues

### Certificate Errors

**Diagnosis:**
```bash
# Test certificate
openssl s_client -connect yourdomain.com:443

# Check Traefik logs
docker logs traefik | grep -i cert
```

**Solutions:**

1. **Certificate expired:**
   - Renew certificate
   - Check auto-renewal is configured

2. **Wrong certificate:**
   - Verify certificate files in traefik/certs/
   - Check certificate matches domain

3. **Let's Encrypt rate limit:**
   - Use staging environment for testing
   - Wait for rate limit reset

---

## Backup / Restore Issues

### Backup Fails

**Diagnosis:**
```bash
# Check backup logs
cat logs/backup.log

# Manually run backup
./scripts/backup-db.sh prod
```

**Solutions:**

1. **Disk full:**
   ```bash
   df -h
   # Free up space
   ```

2. **Database not accessible:**
   - Verify database is running
   - Check connection

### Restore Fails

**Diagnosis:**
```bash
# Check backup file integrity
gunzip -t backup_file.sql.gz

# Check database logs
docker logs db-prod
```

**Solutions:**

1. **Corrupted backup:**
   - Try different backup file
   - Verify backup process

2. **Version mismatch:**
   - Ensure PostgreSQL versions match
   - Update TimescaleDB extension if needed

---

## Migration Issues

### Can't Run Migrations

**Diagnosis:**
```bash
# Check Alembic status
docker compose -f docker-compose.prod.yml exec backend-prod \
  sh -c "ENV_FILE=/app/backend.env uv run alembic current"
```

**Solutions:**

1. **ENV_FILE not set:**
   - Ensure `ENV_FILE=backend.env` is in environment
   - Or use full command with ENV_FILE prefix

2. **Database locked:**
   - Check for long-running transactions
   - Restart database if needed

3. **Migration conflict:**
   - Review git history for migration conflicts
   - Regenerate migration if needed

---

## Getting Help

If you can't resolve an issue:

1. **Gather information:**
   - Full error messages from logs
   - Environment details (OS, Docker version)
   - Steps to reproduce

2. **Check documentation:**
   - README.md
   - CLAUDE.md
   - docs/MONITORING.md

3. **Check container logs:**
   ```bash
   # Save all logs
   docker compose -f docker-compose.prod.yml logs > full-logs.txt
   ```

4. **Export diagnostics:**
   ```bash
   # System info
   docker version > diagnostics.txt
   docker compose version >> diagnostics.txt
   docker ps -a >> diagnostics.txt
   docker network ls >> diagnostics.txt
   ```

---

**Document Version:** 1.0
**Last Updated:** October 2025
