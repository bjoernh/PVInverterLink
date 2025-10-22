# Deployment Checklist

Use this checklist before deploying to each environment to ensure all requirements are met.

## Pre-Deployment Checklist (All Environments)

### Server Preparation

- [ ] Ubuntu 22.04 LTS or newer installed
- [ ] Server has minimum 4 CPU cores, 8 GB RAM, 100 GB storage
- [ ] Docker Engine 24.0+ installed
- [ ] Docker Compose v2.20+ installed
- [ ] Git installed
- [ ] User added to docker group: `sudo usermod -aG docker $USER`

### DNS Configuration

- [ ] DNS A records created and propagated:
  - [ ] `test.yourdomain.com` → Server IP
  - [ ] `staging.yourdomain.com` → Server IP
  - [ ] `yourdomain.com` → Server IP
  - [ ] `signoz.yourdomain.com` → Server IP
- [ ] DNS propagation verified: `dig yourdomain.com +short`

### Firewall Configuration

- [ ] UFW installed and configured
- [ ] SSH port allowed (22)
- [ ] HTTP port allowed (80)
- [ ] HTTPS port allowed (443)
- [ ] Collector port allowed (10000)
- [ ] UFW enabled: `sudo ufw enable`
- [ ] fail2ban installed and running for SSH protection

### Repository Setup

- [ ] Repository cloned with submodules: `git clone --recursive [url]`
- [ ] Latest code pulled: `git pull origin main`
- [ ] Submodules updated: `git submodule update --init --recursive`

### Directory Structure

- [ ] Data directories created: `mkdir -p data/{test,staging,prod}/{postgres,signoz,backups}`
- [ ] Log directories created: `mkdir -p logs/{test,staging,prod}`
- [ ] Traefik directories created: `mkdir -p traefik/{dynamic,certs}`
- [ ] Permissions set: `chmod 700 data logs`

---

## Test Environment Checklist

### Configuration

- [ ] `.env.test` created from `.env.test.example`
- [ ] Strong passwords generated:
  - [ ] `POSTGRES_PASSWORD` (openssl rand -hex 16)
  - [ ] `AUTH_SECRET` (openssl rand -hex 32)
- [ ] `ENCRYPTION_KEY` generated: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] `BASE_URL` set to `http://test.yourdomain.com`
- [ ] `COOKIE_SECURE` set to `False` (HTTP mode)
- [ ] File permissions restricted: `chmod 600 .env.test`

### Deployment

- [ ] Traefik network created: `docker network create traefik-public`
- [ ] Deployment script executed: `./scripts/deploy-test.sh`
- [ ] All containers running: `docker compose -f docker-compose.test.yml ps`
- [ ] Database migrations applied
- [ ] Admin user created

### Verification

- [ ] Health endpoint responding: `curl http://test.yourdomain.com/healthcheck`
- [ ] API docs accessible: `curl -I http://test.yourdomain.com/docs`
- [ ] Admin interface accessible: `curl -I http://test.yourdomain.com/admin`
- [ ] SignOz UI accessible: `curl -I http://signoz.yourdomain.com/test`
- [ ] Can log in with admin credentials
- [ ] Collector listening on port 10000: `netstat -tlnp | grep 10000`

---

## Staging Environment Checklist

### Configuration

- [ ] `.env.staging` created from `.env.staging.example`
- [ ] **Different** passwords from test environment:
  - [ ] `POSTGRES_PASSWORD` (new random password)
  - [ ] `AUTH_SECRET` (new random secret)
  - [ ] `ENCRYPTION_KEY` (new Fernet key)
- [ ] `BASE_URL` set to `http://staging.yourdomain.com`
- [ ] `COOKIE_SECURE` set to `False` (HTTP mode)
- [ ] Email configuration tested (SMTP settings)
- [ ] File permissions restricted: `chmod 600 .env.staging`

### Deployment

- [ ] Deployment script executed: `./scripts/deploy-staging.sh`
- [ ] All containers running: `docker compose -f docker-compose.staging.yml ps`
- [ ] Database migrations applied
- [ ] Admin user created

### Verification

- [ ] Health endpoint responding: `curl http://staging.yourdomain.com/healthcheck`
- [ ] All endpoints accessible
- [ ] SignOz monitoring working
- [ ] Can send and receive emails
- [ ] Data import from test environment (if needed)
- [ ] Full application workflow tested

---

## Production Environment Checklist

### Security Requirements (CRITICAL!)

- [ ] **Strong, unique passwords** (minimum 20 characters):
  - [ ] `POSTGRES_PASSWORD`
  - [ ] `AUTH_SECRET`
  - [ ] `ENCRYPTION_KEY`
  - [ ] `CLICKHOUSE_PASSWORD`
- [ ] All passwords **different** from test and staging
- [ ] `COOKIE_SECURE` set to `True`
- [ ] `BASE_URL` using HTTPS: `https://yourdomain.com`
- [ ] Email sending configured and tested
- [ ] File permissions restricted: `chmod 600 .env.prod`
- [ ] Environment file not committed to git

### SSL/TLS Configuration

- [ ] SSL certificates obtained (Let's Encrypt or custom)
- [ ] Certificates installed in `traefik/certs/`
- [ ] Traefik HTTPS configured
- [ ] Certificate auto-renewal configured (if using Let's Encrypt)
- [ ] HTTPS redirection enabled

### Monitoring Setup

- [ ] SignOz configured with production credentials
- [ ] SMTP alerts configured
- [ ] Alert rules created:
  - [ ] Critical alerts (Tier 1)
  - [ ] Warning alerts (Tier 2)
- [ ] Email alert delivery tested
- [ ] Dashboards created and verified

### Backup Configuration

- [ ] Backup script tested: `./scripts/backup-db.sh prod`
- [ ] Cron job configured for daily backups at 2 AM
- [ ] Backup retention policy verified
- [ ] Test restore performed on staging

### Pre-Deployment Testing

- [ ] All features tested in staging environment
- [ ] Load testing performed (if applicable)
- [ ] Database migration tested on staging
- [ ] Rollback procedure documented and tested
- [ ] Monitoring dashboards reviewed

### Deployment

- [ ] Pre-deployment backup created
- [ ] Deployment script executed: `./scripts/deploy-prod.sh`
- [ ] All containers running: `docker compose -f docker-compose.prod.yml ps`
- [ ] Database migrations applied successfully
- [ ] Admin user created
- [ ] Post-deployment backup created

### Post-Deployment Verification

- [ ] Health endpoint responding: `curl https://yourdomain.com/healthcheck`
- [ ] HTTPS working correctly (no certificate warnings)
- [ ] User login working
- [ ] Data collection working (inverters sending data)
- [ ] SignOz receiving telemetry data
- [ ] No errors in logs
- [ ] Email sending working (test password reset)
- [ ] API endpoints responding correctly
- [ ] Admin interface accessible
- [ ] Monitoring dashboards showing data

### Post-Deployment Monitoring (First 24 Hours)

- [ ] Monitor SignOz dashboard for errors
- [ ] Check backend logs: `docker compose -f docker-compose.prod.yml logs -f backend-prod`
- [ ] Verify data ingestion rate is normal
- [ ] Check database performance metrics
- [ ] Monitor resource usage (CPU, memory, disk)
- [ ] Verify no alert emails triggered
- [ ] Test user workflows

---

## Security Hardening Checklist (Production)

### SSH Security

- [ ] SSH key-based authentication enabled
- [ ] Password authentication disabled: `PasswordAuthentication no` in `/etc/ssh/sshd_config`
- [ ] Root login disabled: `PermitRootLogin no`
- [ ] fail2ban monitoring SSH attempts
- [ ] Non-standard SSH port considered (optional)

### Docker Security

- [ ] Docker daemon socket not exposed
- [ ] Containers run as non-root users
- [ ] Resource limits configured (CPU, memory)
- [ ] Log rotation configured
- [ ] Docker images regularly updated

### Network Security

- [ ] Firewall active and configured
- [ ] Only necessary ports exposed
- [ ] Rate limiting enabled (Traefik)
- [ ] DDoS protection considered (Cloudflare, etc.)

### Application Security

- [ ] Admin interface restricted (IP whitelist or VPN)
- [ ] SignOz UI password-protected
- [ ] Traefik dashboard secured or disabled
- [ ] API rate limiting configured
- [ ] CORS policies configured
- [ ] Security headers enabled (CSP, HSTS, etc.)

### Data Security

- [ ] Database not exposed to internet
- [ ] Backup encryption enabled
- [ ] Secrets not logged
- [ ] PII handling compliant

### Monitoring & Logging

- [ ] Centralized logging configured
- [ ] Security event monitoring enabled
- [ ] Failed login attempts monitored
- [ ] Alert on suspicious activity
- [ ] Log retention policy defined

---

## Maintenance Checklist

### Daily

- [ ] Check monitoring dashboard
- [ ] Review error logs
- [ ] Verify backups completed
- [ ] Check disk space

### Weekly

- [ ] Review resource usage trends
- [ ] Check for security updates
- [ ] Review slow queries
- [ ] Test backup restore (monthly)

### Monthly

- [ ] Review user access
- [ ] Analyze performance trends
- [ ] Update dependencies
- [ ] Review and update documentation

### Quarterly

- [ ] Security audit
- [ ] Disaster recovery drill
- [ ] Capacity planning review
- [ ] Update SSL certificates (if not auto-renewed)

---

## Rollback Checklist

If deployment fails or issues are discovered:

- [ ] Stop affected services
- [ ] Restore pre-deployment database backup
- [ ] Revert code to previous version: `git checkout [commit]`
- [ ] Rebuild and restart services
- [ ] Verify functionality restored
- [ ] Document issue and root cause
- [ ] Create post-mortem report

---

## Emergency Contact Information

Maintain a list of emergency contacts:

- **Primary Administrator**: [Name, Phone, Email]
- **Backup Administrator**: [Name, Phone, Email]
- **Hosting Provider Support**: [Phone, Email]
- **DNS Provider Support**: [Phone, Email]
- **SSL Certificate Provider**: [Phone, Email]

---

## Sign-Off

### Test Environment

- Deployed by: ________________
- Date: ________________
- Verified by: ________________
- Date: ________________

### Staging Environment

- Deployed by: ________________
- Date: ________________
- Verified by: ________________
- Date: ________________

### Production Environment

- Deployed by: ________________
- Date: ________________
- Verified by: ________________
- Date: ________________
- Approved by: ________________
- Date: ________________

---

**Document Version:** 1.0
**Last Updated:** October 2025
