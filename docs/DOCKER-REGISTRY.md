# Docker Registry Guide

> Comprehensive guide for building, pushing, and deploying Docker images using git.64b.de registry

## Table of Contents

1. [Overview](#overview)
2. [Registry Information](#registry-information)
3. [Authentication](#authentication)
4. [CI/CD Automated Builds](#cicd-automated-builds)
5. [Manual Building and Pushing](#manual-building-and-pushing)
6. [Image Tagging Strategy](#image-tagging-strategy)
7. [Pulling Images for Deployment](#pulling-images-for-deployment)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

---

## Overview

This project uses a Docker registry for storing and distributing container images across different environments (test, staging, production). Images are built automatically via CI/CD and can also be built manually when needed.

### Benefits

- **Consistent deployments**: Same image across all environments
- **Fast deployments**: Pull pre-built images instead of building on servers
- **Version control**: Track exact versions with semantic tags and commit SHAs
- **Rollback capability**: Easily revert to previous versions
- **Build once, deploy many**: Single build artifact used everywhere

---

## Registry Information

| Property | Value |
|----------|-------|
| **Registry URL** | `git.64b.de` |
| **Image Name** | `bjoern/deye_hard` |
| **Full Image Path** | `git.64b.de/bjoern/deye_hard` |
| **Authentication** | Username/Password |

---

## Authentication

### Setting Up Credentials

#### For Local Development/Manual Builds

```bash
# Set environment variables
export DOCKER_REGISTRY_USERNAME="your-username"
export DOCKER_REGISTRY_PASSWORD="your-password-or-token"

# Login to registry
echo "$DOCKER_REGISTRY_PASSWORD" | docker login git.64b.de -u "$DOCKER_REGISTRY_USERNAME" --password-stdin
```

#### For CI/CD (GitHub Actions)

Configure these secrets in your GitHub repository:

1. Go to repository **Settings** → **Secrets and variables** → **Actions**
2. Add the following secrets:
   - `DOCKER_REGISTRY_USERNAME`: Your registry username
   - `DOCKER_REGISTRY_PASSWORD`: Your registry password or access token

#### For Deployment Servers

```bash
# Option 1: Set environment variables in shell profile (~/.bashrc or ~/.zshrc)
export DOCKER_REGISTRY_USERNAME="deploy-user"
export DOCKER_REGISTRY_PASSWORD="deploy-token"

# Option 2: Create a credentials file (more secure)
# Store credentials in a secure location
echo "export DOCKER_REGISTRY_USERNAME='deploy-user'" >> ~/.docker-credentials
echo "export DOCKER_REGISTRY_PASSWORD='deploy-token'" >> ~/.docker-credentials
chmod 600 ~/.docker-credentials

# Source before deployment
source ~/.docker-credentials
deployment/scripts/deploy-prod.sh
```

### Verifying Authentication

```bash
# Test login
docker login git.64b.de -u "$DOCKER_REGISTRY_USERNAME"

# Verify with a pull command
docker pull git.64b.de/bjoern/deye_hard:latest
```

---

## CI/CD Automated Builds

The project includes a GitHub Actions workflow that automatically builds and pushes Docker images.

### Workflow File

Location: `.github/workflows/docker-build-push.yml`

### Automatic Triggers

Images are built automatically when:

1. **Pushing to main/master branch**
   - Creates tags: `latest`, `main`, `sha-<commit>`

2. **Pushing to deployment branch**
   - Creates tags: `deployment`, `sha-<commit>`

3. **Creating a semantic version tag** (e.g., `v1.2.3`)
   - Creates tags: `v1.2.3`, `v1.2`, `v1`, `prod`, `sha-<commit>`

4. **Pushing to any other branch**
   - Creates tags: `<branch-name>`, `test`, `sha-<commit>`

### Manual Trigger

You can manually trigger a build via GitHub Actions:

1. Go to **Actions** tab in GitHub
2. Select "Build and Push Docker Image" workflow
3. Click **Run workflow**
4. Choose:
   - Target environment (test/staging/prod)
   - Optional custom tag
5. Click **Run workflow**

### Viewing Build Status

- Check the **Actions** tab for build progress
- Build logs show all tags that were pushed
- Failed builds will display error messages

---

## Manual Building and Pushing

### Using the Build Script

The easiest way to manually build and push images:

```bash
# Build and push with default 'latest' tag
deployment/scripts/build-and-push.sh

# Build and push with custom tag
deployment/scripts/build-and-push.sh v1.2.3

# Build and push for specific environment
deployment/scripts/build-and-push.sh --env test
deployment/scripts/build-and-push.sh --env staging
deployment/scripts/build-and-push.sh --env prod
```

### Manual Docker Commands

If you prefer using Docker commands directly:

```bash
# 1. Login to registry
docker login git.64b.de -u "$DOCKER_REGISTRY_USERNAME"

# 2. Build the image
docker build \
  --tag git.64b.de/bjoern/deye_hard:v1.2.3 \
  --tag git.64b.de/bjoern/deye_hard:latest \
  .

# 3. Push to registry
docker push git.64b.de/bjoern/deye_hard:v1.2.3
docker push git.64b.de/bjoern/deye_hard:latest
```

### Build Arguments and Labels

The build automatically includes metadata labels:

```bash
docker build \
  --label "org.opencontainers.image.title=Deye Hard Backend" \
  --label "org.opencontainers.image.version=v1.2.3" \
  --label "org.opencontainers.image.created=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
  --tag git.64b.de/bjoern/deye_hard:v1.2.3 \
  .
```

---

## Image Tagging Strategy

### Tag Types

| Tag Format | Example | Purpose | When Created |
|------------|---------|---------|--------------|
| `latest` | `latest` | Most recent build from main | Push to main/master |
| `main` | `main` | Latest main branch build | Push to main |
| `test` | `test` | Test environment | Push to non-main branches |
| `staging` | `staging` | Staging environment | Manual or workflow dispatch |
| `prod` | `prod` | Production environment | Semantic version tags |
| `v{major}.{minor}.{patch}` | `v1.2.3` | Semantic version | Git tag (v*) |
| `v{major}.{minor}` | `v1.2` | Minor version | Git tag (v*) |
| `v{major}` | `v1` | Major version | Git tag (v*) |
| `sha-{commit}` | `sha-abc1234` | Specific commit | Every build |
| `{branch}` | `feat-xyz` | Branch-specific | Push to branch |

### Environment-Specific Tags

**Test Environment:**
- Use: `test`, `sha-xxxxx`, or branch names
- Purpose: Bleeding-edge testing
- Update frequency: Every commit

**Staging Environment:**
- Use: `staging`, `v1.x.x-rc.1`, or `sha-xxxxx`
- Purpose: Pre-release verification
- Update frequency: Release candidates

**Production Environment:**
- Use: `v1.x.x` (semantic versions) or `prod`
- Purpose: Stable releases only
- Update frequency: Controlled releases
- ⚠️ **NEVER** use `latest`, `test`, or `sha-xxxxx` in production!

### Creating Semantic Version Tags

```bash
# 1. Ensure you're on main/master branch
git checkout main
git pull

# 2. Create and push a semantic version tag
git tag v1.2.3
git push origin v1.2.3

# 3. CI/CD will automatically build and push with tags:
#    - v1.2.3
#    - v1.2
#    - v1
#    - prod
#    - sha-<commit>
```

---

## Pulling Images for Deployment

### Using Deployment Scripts

The deployment scripts automatically pull the correct image tag:

```bash
# Test environment (pulls 'test' tag by default)
deployment/scripts/deploy-test.sh

# Staging environment (pulls 'staging' tag by default)
deployment/scripts/deploy-staging.sh

# Production environment (pulls 'prod' tag by default)
deployment/scripts/deploy-prod.sh

# Override with specific tag
IMAGE_TAG=v1.2.3 deployment/scripts/deploy-prod.sh
IMAGE_TAG=sha-abc1234 deployment/scripts/deploy-test.sh
```

### Manual Docker Compose

```bash
# Set the image tag
export IMAGE_TAG=v1.2.3

# Pull the image
docker compose -f deployment/docker-compose.prod.yml pull

# Start services
docker compose -f deployment/docker-compose.prod.yml up -d
```

### Direct Docker Pull

```bash
# Pull specific version
docker pull git.64b.de/bjoern/deye_hard:v1.2.3

# Pull latest
docker pull git.64b.de/bjoern/deye_hard:latest

# Pull by commit SHA
docker pull git.64b.de/bjoern/deye_hard:sha-abc1234
```

### Inspecting Image Information

```bash
# View image labels and metadata
docker inspect git.64b.de/bjoern/deye_hard:v1.2.3

# View creation date and version
docker inspect git.64b.de/bjoern/deye_hard:v1.2.3 | jq '.[0].Config.Labels'

# List all local images
docker images git.64b.de/bjoern/deye_hard
```

---

## Troubleshooting

### Authentication Failures

**Problem:** `unauthorized: authentication required`

```bash
# Solution 1: Verify credentials
echo $DOCKER_REGISTRY_USERNAME
echo $DOCKER_REGISTRY_PASSWORD

# Solution 2: Re-login
docker logout git.64b.de
docker login git.64b.de -u "$DOCKER_REGISTRY_USERNAME"

# Solution 3: Check password special characters
# If password contains special chars, use quotes:
echo 'password-with-$pecial-chars' | docker login git.64b.de -u "username" --password-stdin
```

### Image Not Found

**Problem:** `Error response from daemon: pull access denied ... repository does not exist`

```bash
# Check image name spelling
docker pull git.64b.de/bjoern/deye_hard:v1.2.3
#                      ^^^^^^^^^^^^^^ ensure correct path

# Verify tag exists in registry (if you have web access)
# Or try pulling a known tag like 'latest'
docker pull git.64b.de/bjoern/deye_hard:latest

# Check if tag was actually pushed
# Review CI/CD logs in GitHub Actions
```

### Network/Connectivity Issues

**Problem:** `dial tcp: lookup git.64b.de: no such host`

```bash
# Test DNS resolution
nslookup git.64b.de
ping git.64b.de

# Test HTTPS connectivity
curl -I https://git.64b.de

# Check Docker daemon DNS settings
cat /etc/docker/daemon.json

# Try with explicit DNS
# Edit /etc/docker/daemon.json:
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}

# Restart Docker
sudo systemctl restart docker
```

### Build Failures in CI/CD

**Problem:** GitHub Actions build fails

1. **Check Build Logs:**
   - Go to Actions tab
   - Click on failed workflow
   - Expand failed steps

2. **Common Issues:**
   ```bash
   # Missing secrets
   # → Add DOCKER_REGISTRY_USERNAME and DOCKER_REGISTRY_PASSWORD in Settings

   # Build context errors
   # → Ensure .dockerignore is correctly configured

   # Out of disk space
   # → GitHub runners have limited space; optimize image size
   ```

3. **Retry Build:**
   - Click "Re-run jobs" in GitHub Actions
   - Or push a new commit

### Slow Image Pulls

**Problem:** Image pulls taking too long

```bash
# Enable parallel downloads
# Edit /etc/docker/daemon.json:
{
  "max-concurrent-downloads": 10
}

# Restart Docker
sudo systemctl restart docker

# Use pull-through cache (advanced)
# Configure a local registry mirror
```

### Disk Space Issues

**Problem:** `no space left on device`

```bash
# Remove unused images
docker image prune -a

# Remove unused containers
docker container prune

# Remove unused volumes
docker volume prune

# Clean everything (caution!)
docker system prune -a --volumes

# Check disk usage
docker system df
```

---

## Best Practices

### For Developers

1. **Always tag commits before releases:**
   ```bash
   git tag v1.2.3
   git push origin v1.2.3
   ```

2. **Use semantic versioning:**
   - Major: Breaking changes (v2.0.0)
   - Minor: New features (v1.2.0)
   - Patch: Bug fixes (v1.2.1)

3. **Test before tagging:**
   - Build and test locally
   - Deploy to test environment
   - Verify in staging
   - Only then create production tag

4. **Keep images small:**
   - Regularly review .dockerignore
   - Use multi-stage builds if needed
   - Remove unnecessary dependencies

### For Operators

1. **Always specify exact versions in production:**
   ```bash
   # Good
   IMAGE_TAG=v1.2.3 deployment/scripts/deploy-prod.sh

   # Bad - don't use in production
   IMAGE_TAG=latest deployment/scripts/deploy-prod.sh
   ```

2. **Maintain deployment records:**
   ```bash
   # Log deployments
   echo "$(date): Deployed v1.2.3 to production" >> deployment-log.txt
   ```

3. **Test rollback procedures:**
   ```bash
   # Practice rolling back before you need it
   IMAGE_TAG=v1.2.2 deployment/scripts/deploy-prod.sh
   ```

4. **Monitor image sizes:**
   ```bash
   # Regularly check image sizes
   docker images git.64b.de/bjoern/deye_hard --format "table {{.Tag}}\t{{.Size}}"
   ```

### Security

1. **Rotate registry credentials regularly**
2. **Use read-only tokens for deployment servers** (if supported)
3. **Never commit credentials to git**
4. **Restrict registry access** to authorized users only
5. **Scan images for vulnerabilities** before deploying to production

### CI/CD

1. **Monitor build times** - optimize if builds take too long
2. **Set up notifications** for failed builds
3. **Use build caching** to speed up builds (already configured)
4. **Review build logs** periodically for warnings

---

## Quick Reference

### Common Commands

```bash
# Login
docker login git.64b.de

# Build and push
deployment/scripts/build-and-push.sh v1.2.3

# Deploy with specific version
IMAGE_TAG=v1.2.3 deployment/scripts/deploy-prod.sh

# Pull specific image
docker pull git.64b.de/bjoern/deye_hard:v1.2.3

# List tags
docker images git.64b.de/bjoern/deye_hard

# Clean up
docker image prune -a
```

### Environment Variables

```bash
# Required for registry authentication
DOCKER_REGISTRY_USERNAME="your-username"
DOCKER_REGISTRY_PASSWORD="your-password"

# Required for deployment
IMAGE_TAG="v1.2.3"  # or test, staging, prod, sha-xxxxx
```

### URLs

- **Registry:** https://git.64b.de
- **GitHub Actions:** https://github.com/YOUR_REPO/actions
- **Image Path:** git.64b.de/bjoern/deye_hard

---

**Last Updated:** October 2025
**Maintainer:** WTF Kooperative eG
