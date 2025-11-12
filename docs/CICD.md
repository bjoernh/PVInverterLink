# CI/CD Pipeline - GitHub Actions

> Automated Docker image builds and deployments using GitHub Actions and GitHub Container Registry (ghcr.io)

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [GitHub Actions Workflow](#github-actions-workflow)
4. [Image Tagging Strategy](#image-tagging-strategy)
5. [Triggering Builds](#triggering-builds)
6. [Deployment Workflow](#deployment-workflow)
7. [Registry Authentication](#registry-authentication)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The project uses **GitHub Actions** for continuous integration and continuous deployment (CI/CD). Every code change triggers an automated build that creates Docker images and pushes them to **GitHub Container Registry (ghcr.io)**.

### Registry Information

| Property | Value |
|----------|-------|
| **Registry** | `ghcr.io` (GitHub Container Registry) |
| **Backend Image** | `ghcr.io/bjoernh/pvinverterlink` |
| **Collector Image** | `ghcr.io/bjoernh/solarmancollector` |
| **Authentication** | GitHub Token (automatic in Actions) |
| **Visibility** | Public |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Developer                                                       │
│ • Commits code                                                  │
│ • Creates git tag (v1.2.3)                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ git push / git push --tags
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ GitHub Repository (https://github.com/bjoernh/PVInverterLink)   │
│ • Code storage                                                  │
│ • Workflow triggers                                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Triggers GitHub Actions
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ GitHub Actions Workflow (.github/workflows/docker-build-push.yml)│
│ • Build Docker image                                             │
│ • Tag with semantic version, SHA, environment tags               │
│ • Push to ghcr.io                                                │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             │ Docker push
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ GitHub Container Registry (ghcr.io)                             │
│ • ghcr.io/bjoernh/pvinverterlink:v1.2.3                         │
│ • ghcr.io/bjoernh/pvinverterlink:sha-abc1234                    │
│ • ghcr.io/bjoernh/pvinverterlink:latest                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ docker pull
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Deployment Servers (Test / Staging / Production)                │
│ • Pull image from ghcr.io                                       │
│ • Start containers                                              │
│ • Run migrations                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## GitHub Actions Workflow

### Workflow File

**Location**: `.github/workflows/docker-build-push.yml`

### Triggers

The workflow is triggered by:

1. **Git Tag Push** (Recommended for releases)
   ```bash
   git tag v1.2.3
   git push origin v1.2.3
   ```

2. **Manual Trigger** (workflow_dispatch)
   - Go to: GitHub → Actions → "Build and Push Docker Image" → "Run workflow"
   - Select environment: test, staging, or prod
   - Optionally specify a custom tag

### Workflow Steps

```yaml
name: Build and Push Docker Image

on:
  push:
    tags:
      - '**'  # Triggered on any tag
  workflow_dispatch:
    inputs:
      environment: # test, staging, prod
      custom_tag:  # Optional custom tag

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: bjoernh/pvinverterlink

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Set up Docker Buildx
      - Log in to GitHub Container Registry
      - Extract metadata (tags, labels)
      - Build and push Docker image
      - Generate deployment summary
```

### What Gets Built

For each trigger, the workflow:

1. **Checks out** the repository code
2. **Sets up** Docker Buildx (for advanced builds)
3. **Logs in** to ghcr.io using `GITHUB_TOKEN`
4. **Generates tags** based on the trigger type:
   - Git tag `v1.2.3` → Creates: `v1.2.3`, `v1.2`, `v1`, `latest`, `sha-abc1234`
   - Manual trigger → Creates: `test`/`staging`/`prod`, `sha-abc1234`
5. **Builds** the Docker image from `Dockerfile`
6. **Pushes** all tags to ghcr.io
7. **Outputs** a summary with pull commands

### Build Time

- **Typical build time**: 3-5 minutes
- **With cache**: 1-2 minutes
- **First build (no cache)**: 5-8 minutes

---

## Image Tagging Strategy

### Tag Types

| Tag Format | Example | When Created | Use Case |
|------------|---------|--------------|----------|
| **Semantic Version** | `v1.2.3` | Git tag `v1.2.3` | Production releases |
| **Major Version** | `v1` | Git tag `v1.x.x` | Track major version |
| **Minor Version** | `v1.2` | Git tag `v1.2.x` | Track minor version |
| **Latest** | `latest` | Any git tag | Latest tagged release |
| **Commit SHA** | `sha-abc1234` | Every build | Exact commit tracking |
| **Environment** | `test`, `staging`, `prod` | Manual trigger | Environment-specific |

### Version Tagging Examples

**Creating a release:**

```bash
# Create and push a semantic version tag
git tag v1.2.3
git push origin v1.2.3

# This creates the following tags in ghcr.io:
# - ghcr.io/bjoernh/pvinverterlink:v1.2.3
# - ghcr.io/bjoernh/pvinverterlink:v1.2
# - ghcr.io/bjoernh/pvinverterlink:v1
# - ghcr.io/bjoernh/pvinverterlink:latest
# - ghcr.io/bjoernh/pvinverterlink:sha-abc1234
```

**Creating a release candidate:**

```bash
# For testing before production
git tag v1.2.3-rc.1
git push origin v1.2.3-rc.1

# This creates:
# - ghcr.io/bjoernh/pvinverterlink:v1.2.3-rc.1
# - ghcr.io/bjoernh/pvinverterlink:sha-abc1234
```

### Recommended Tag Strategy

| Environment | Recommended Tag | Alternative |
|-------------|----------------|-------------|
| **Test** | `sha-abc1234` | `test` (manual trigger) |
| **Staging** | `v1.2.3-rc.1` | `staging` (manual trigger) |
| **Production** | `v1.2.3` | `v1.2`, `v1` |

⚠️ **Never use** `latest` or `test` tags in production!

---

## Triggering Builds

### Method 1: Git Tags (Recommended)

**For production releases:**

```bash
# Ensure you're on the main branch
git checkout main
git pull origin main

# Create a semantic version tag
git tag v1.2.3

# Push the tag to trigger the build
git push origin v1.2.3

# Monitor the build at:
# https://github.com/bjoernh/PVInverterLink/actions
```

### Method 2: Manual Trigger (GitHub UI)

**For test/staging deployments:**

1. Navigate to: https://github.com/bjoernh/PVInverterLink/actions
2. Click "Build and Push Docker Image" workflow
3. Click "Run workflow" button
4. Select:
   - **Branch**: Usually `main`
   - **Environment**: `test`, `staging`, or `prod`
   - **Custom tag** (optional): Any custom tag name
5. Click "Run workflow"

### Method 3: GitHub CLI (Advanced)

```bash
# Install GitHub CLI if not already installed
# https://cli.github.com/

# Trigger a test build
gh workflow run docker-build-push.yml \
  -f environment=test

# Trigger a staging build with custom tag
gh workflow run docker-build-push.yml \
  -f environment=staging \
  -f custom_tag=staging-v1.2.3-rc.1
```

---

## Deployment Workflow

### Complete Release Workflow

```bash
# ============================================================
# 1. PREPARE RELEASE
# ============================================================

# Ensure you're on main and up to date
git checkout main
git pull origin main

# Run tests locally
uv run pytest

# Update version numbers if needed (pyproject.toml, etc.)
# Commit any final changes
git add .
git commit -m "chore: prepare release v1.2.3"
git push origin main

# ============================================================
# 2. BUILD & PUSH IMAGE (via GitHub Actions)
# ============================================================

# Create and push semantic version tag
git tag v1.2.3
git push origin v1.2.3

# Wait for GitHub Actions to build (3-5 minutes)
# Monitor: https://github.com/bjoernh/PVInverterLink/actions

# ============================================================
# 3. DEPLOY TO TEST ENVIRONMENT
# ============================================================

# SSH to test server
ssh user@test-server

# Set registry credentials (if not already set)
export DOCKER_REGISTRY_USERNAME="your-github-username"
export DOCKER_REGISTRY_PASSWORD="your-github-token"

# Deploy with the new version
export IMAGE_TAG="v1.2.3"
cd /path/to/deployment
./deployment/scripts/deploy-test.sh

# Verify deployment
curl http://test.solar.64b.de/healthcheck

# Test the application thoroughly

# ============================================================
# 4. DEPLOY TO STAGING ENVIRONMENT
# ============================================================

# SSH to staging server
ssh user@staging-server

# Deploy same version
export IMAGE_TAG="v1.2.3"
cd /path/to/deployment
./deployment/scripts/deploy-staging.sh

# Verify and test
curl http://staging.solar.64b.de/healthcheck

# ============================================================
# 5. DEPLOY TO PRODUCTION
# ============================================================

# SSH to production server
ssh user@production-server

# Deploy to production (requires confirmation)
export IMAGE_TAG="v1.2.3"
cd /path/to/deployment
./deployment/scripts/deploy-prod.sh

# Script will ask for confirmation:
# "Are you sure you want to continue? Type 'yes' to proceed:"

# Verify production deployment
curl https://solar.64b.de/healthcheck

# Monitor SignOz dashboard for errors
# Monitor logs for 30 minutes

# ============================================================
# 6. POST-DEPLOYMENT
# ============================================================

# Create GitHub release (optional)
gh release create v1.2.3 \
  --title "Release v1.2.3" \
  --notes "Release notes here"

# Update documentation if needed
# Notify users of new features/fixes
```

---

## Registry Authentication

### For GitHub Actions (Automatic)

GitHub Actions automatically authenticates using `GITHUB_TOKEN`:

```yaml
- name: Log in to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

No manual configuration required! ✅

### For Deployment Servers (Manual)

**Option 1: Using Personal Access Token (Recommended)**

1. Create a GitHub Personal Access Token:
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: `read:packages`, `write:packages`
   - Copy the token (you won't see it again!)

2. Log in on deployment server:

```bash
export DOCKER_REGISTRY_USERNAME="your-github-username"
export DOCKER_REGISTRY_PASSWORD="ghp_xxxxxxxxxxxxx"  # Your PAT

echo "$DOCKER_REGISTRY_PASSWORD" | \
  docker login ghcr.io -u "$DOCKER_REGISTRY_USERNAME" --password-stdin
```

3. Add to deployment environment:

```bash
# Add to ~/.bashrc or ~/.profile
export DOCKER_REGISTRY_USERNAME="your-github-username"
export DOCKER_REGISTRY_PASSWORD="ghp_xxxxxxxxxxxxx"
```

**Option 2: Using GitHub CLI**

```bash
# Install GitHub CLI
# https://cli.github.com/

# Authenticate
gh auth login

# Configure Docker to use GitHub CLI
gh auth setup-git
```

### Verifying Authentication

```bash
# Test pulling an image
docker pull ghcr.io/bjoernh/pvinverterlink:latest

# Check authentication status
docker info | grep -A 3 "Username"
```

---

## Best Practices

### Version Numbering

Follow **Semantic Versioning** (semver.org):

```
v<MAJOR>.<MINOR>.<PATCH>

Example: v1.2.3
         │ │ │
         │ │ └─ PATCH: Bug fixes
         │ └─── MINOR: New features (backward compatible)
         └───── MAJOR: Breaking changes
```

**Guidelines:**

- ✅ Use `v` prefix: `v1.2.3` (not `1.2.3`)
- ✅ Start at `v1.0.0` for first production release
- ✅ Use `-rc.1` suffix for release candidates: `v1.2.3-rc.1`
- ✅ Use `-beta.1` for beta releases: `v1.2.0-beta.1`

### Tag Hygiene

**DO:**

- ✅ Create tags only from `main` branch
- ✅ Test thoroughly before tagging
- ✅ Write clear release notes
- ✅ Use lightweight tags: `git tag v1.2.3`
- ✅ Push tags explicitly: `git push origin v1.2.3`

**DON'T:**

- ❌ Delete and recreate tags (confusing)
- ❌ Tag untested code
- ❌ Skip version numbers
- ❌ Use arbitrary tag names

### Deployment Safety

```bash
# SAFE: Deploy specific versions
export IMAGE_TAG="v1.2.3"
./deploy-prod.sh

# DANGEROUS: Deploy floating tags
export IMAGE_TAG="latest"  # ❌ Don't do this!
./deploy-prod.sh
```

### Image Cleanup

GitHub Container Registry has **unlimited storage** for public packages, but you should periodically clean old images:

```bash
# Use GitHub CLI to list package versions
gh api /user/packages/container/pvinverterlink/versions

# Delete old versions (manually or via script)
gh api -X DELETE /user/packages/container/pvinverterlink/versions/VERSION_ID
```

**Retention suggestions:**

- Keep all semantic version tags (`v1.2.3`)
- Keep last 10 SHA tags
- Delete old `test`, `staging` tags after release

---

## Troubleshooting

### Build Fails in GitHub Actions

**Problem**: Workflow fails during build

**Diagnosis**:

1. Check GitHub Actions logs:
   - https://github.com/bjoernh/PVInverterLink/actions
   - Click on the failed workflow run
   - Expand the failing step

2. Common causes:
   - Dockerfile syntax error
   - Missing dependencies
   - Build timeout (>6 hours)

**Solution**:

```bash
# Test build locally first
docker build -t test-build .

# If successful locally, check GitHub Actions YAML syntax
# Use GitHub's workflow validator or yamllint
```

### Cannot Pull Image on Deployment Server

**Problem**: `docker pull ghcr.io/bjoernh/pvinverterlink:v1.2.3` fails

**Diagnosis**:

```bash
# Check authentication
docker login ghcr.io -u your-username

# Try pulling latest
docker pull ghcr.io/bjoernh/pvinverterlink:latest

# Check image exists on ghcr.io
curl -H "Authorization: token YOUR_PAT" \
  https://ghcr.io/v2/bjoernh/pvinverterlink/tags/list
```

**Solutions**:

1. **Authentication failed**:
   ```bash
   # Regenerate GitHub Personal Access Token
   # Ensure it has read:packages scope
   ```

2. **Image doesn't exist**:
   ```bash
   # Check GitHub Actions completed successfully
   # Verify tag was pushed: git ls-remote --tags origin
   ```

3. **Network issues**:
   ```bash
   # Check connectivity to ghcr.io
   curl -I https://ghcr.io

   # Check DNS resolution
   nslookup ghcr.io
   ```

### Wrong Image Version Deployed

**Problem**: Deployed wrong version to production

**Solution**:

```bash
# Quick rollback to previous version
export IMAGE_TAG="v1.2.2"  # Previous working version
./deployment/scripts/deploy-prod.sh

# Verify rollback
curl https://solar.64b.de/healthcheck
docker ps | grep backend-prod
docker inspect backend-prod | grep Image
```

### Build Takes Too Long

**Problem**: GitHub Actions build takes >10 minutes

**Solutions**:

1. **Enable layer caching** (already configured):
   ```yaml
   cache-from: type=registry,ref=ghcr.io/bjoernh/pvinverterlink:buildcache
   cache-to: type=registry,ref=ghcr.io/bjoernh/pvinverterlink:buildcache,mode=max
   ```

2. **Optimize Dockerfile**:
   - Use multi-stage builds
   - Order layers from least to most frequently changed
   - Combine RUN commands to reduce layers

3. **Check .dockerignore**:
   ```bash
   # Ensure large files are excluded
   cat .dockerignore
   ```

### Tag Already Exists Error

**Problem**: `git push origin v1.2.3` fails - tag already exists

**Diagnosis**:

```bash
# List existing tags
git tag -l

# Check if tag exists remotely
git ls-remote --tags origin | grep v1.2.3
```

**Solution**:

```bash
# Option 1: Use next version number
git tag v1.2.4
git push origin v1.2.4

# Option 2: Delete and recreate (only if not yet deployed!)
git tag -d v1.2.3                    # Delete local
git push origin :refs/tags/v1.2.3   # Delete remote
git tag v1.2.3                       # Recreate
git push origin v1.2.3               # Push again

# ⚠️ WARNING: Only delete tags that haven't been deployed!
```

---

## Additional Resources

- **GitHub Container Registry Docs**: https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Docker Build Push Action**: https://github.com/docker/build-push-action
- **Semantic Versioning**: https://semver.org/

## Related Documentation

- [DOCKER-REGISTRY.md](DOCKER-REGISTRY.md) - Comprehensive registry documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Server deployment procedures
- [DEPLOYMENT-CHECKLIST.md](DEPLOYMENT-CHECKLIST.md) - Pre-deployment checklist
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - General troubleshooting guide
- [MONITORING.md](MONITORING.md) - Monitoring and observability

---

**Last Updated**: November 2025
**Maintained By**: Development Team
**Repository**: https://github.com/bjoernh/PVInverterLink
