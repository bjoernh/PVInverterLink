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

- [ ] Repository cloned with submodules: `git clone --recursive https://github.com/bjoernh/PVInverterLink.git`
- [ ] Latest code pulled: `git pull origin main`

### GitHub Container Registry Authentication

- [ ] GitHub Personal Access Token (PAT) created with `read:packages` scope:
  - [ ] Go to: https://github.com/settings/tokens
  - [ ] Generate new token (classic)
  - [ ] Select scope: `read:packages`
  - [ ] Copy token securely
- [ ] Registry credentials set as environment variables:
  - [ ] `export DOCKER_REGISTRY_USERNAME="your-github-username"`
  - [ ] `export DOCKER_REGISTRY_PASSWORD="ghp_xxxxx"` (your PAT)
- [ ] Docker login to ghcr.io successful: `docker login ghcr.io`
- [ ] Test pull: `docker pull ghcr.io/bjoernh/pvinverterlink:latest`


### CI/CD & Image Versioning

- [ ] GitHub Actions workflow verified: https://github.com/bjoernh/PVInverterLink/actions
- [ ] Latest image build successful
- [ ] Image tag determined for deployment:
  - [ ] Test: `test` or `sha-abc1234`
  - [ ] Staging: `v1.2.3-rc.1` or `staging`
  - [ ] Production: `v1.2.3` (semantic version only!)
- [ ] Image exists in registry: `docker pull ghcr.io/bjoernh/pvinverterlink:${IMAGE_TAG}`
- [ ] `IMAGE_TAG` environment variable set: `export IMAGE_TAG="v1.2.3"`

**📖 See [CICD.md](CICD.md) for complete CI/CD documentation**

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
- [ ] Registry credentials configured (see "GitHub Container Registry Authentication" above)
- [ ] Image tag set: `export IMAGE_TAG="test"` (or specific SHA)
- [ ] Deployment script executed: `./deployment/scripts/deploy-test.sh`
- [ ] Image pulled from ghcr.io successfully
- [ ] All containers running: `docker compose -f deployment/docker-compose.test.yml ps`
- [ ] Database migrations applied
- [ ] Admin user created

### Verification

- [ ] Health endpoint responding: `curl http://test.yourdomain.com/healthcheck`
- [ ] API docs accessible: `curl -I http://test.yourdomain.com/docs`
- [ ] Admin interface accessible: `curl -I http://test.yourdomain.com/admin`
- [ ] SignOz UI accessible: `curl -I http://signoz.yourdomain.com/test`
- [ ] Can log in with admin credentials
- [ ] Collector listening on port 10000: `netstat -tlnp | grep 10000`

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

### Network Security

- [ ] Firewall active and configured
- [ ] Only necessary ports exposed
- [ ] Rate limiting enabled (Traefik)
- [ ] DDoS protection considered (Cloudflare, etc.)

### Application Security

- [ ] Admin interface restricted (IP whitelist or VPN)
- [ ] SignOz UI password-protected
- [ ] Traefik dashboard secured or disabled
- [ ] /docs is password protected
- [ ] API rate limiting configured
- [ ] CORS policies configured
- [ ] Security headers enabled (CSP, HSTS, etc.)

### Data Security

- [ ] Database not exposed to internet
- [ ] Secrets not logged

### Monitoring & Logging

- [ ] Centralized logging configured
- [ ] Security event monitoring enabled
- [ ] Failed login attempts monitored
- [ ] Alert on suspicious activity
- [ ] Log retention policy defined

---

## Rollback Checklist

If deployment fails or issues are discovered:

- [ ] Stop affected services
- [ ] Restore pre-deployment database backup
- [ ] Deploy previous image version: `export IMAGE_TAG="v1.2.2"` (previous working version)
- [ ] Re-run deployment script: `./deployment/scripts/deploy-[environment].sh`
- [ ] Verify image rollback: `docker inspect [container] | grep Image`
- [ ] Verify functionality restored
- [ ] Monitor for errors
- [ ] Document issue and root cause
- [ ] Create post-mortem report

**Note:** With ghcr.io registry, rollbacks are fast (pull previous image, no rebuild needed)

---

**Document Version:** 2.0
**Last Updated:** November 2025
**Changes:** Added GitHub Container Registry (ghcr.io) authentication and CI/CD workflow integration
