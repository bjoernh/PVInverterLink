# Docker Registry Deployment - Implementation Summary

## Overview

This branch (`feat/docker-registry-deployment`) implements automated Docker image builds and registry-based deployments for the Deye Hard Backend project.

## Registry Information

- **Registry URL**: `git.64b.de`
- **Image Path**: `git.64b.de/bjoern/deye_hard`
- **Authentication**: Username/Password

## Changes Made

### 1. CI/CD Pipeline

**File Created**: `.github/workflows/docker-build-push.yml`

- Automated Docker image builds on push to any branch
- Automatic tagging based on branch/commit/semantic version
- Multi-tag support (latest, main, test, staging, prod, sha-xxxxx, v1.2.3)
- GitHub Actions workflow with manual trigger support

### 2. Docker Compose Updates

**Files Modified**:
- `deployment/docker-compose.test.yml`
- `deployment/docker-compose.staging.yml`
- `deployment/docker-compose.prod.yml`

**Changes**:
- Replaced `build:` sections with `image: git.64b.de/bjoern/deye_hard:${IMAGE_TAG}`
- Added `pull_policy: always`
- Environment-specific default tags

### 3. Deployment Scripts

**Files Modified**:
- `deployment/scripts/deploy-test.sh`
- `deployment/scripts/deploy-staging.sh`
- `deployment/scripts/deploy-prod.sh`

**Enhancements**:
- Docker registry authentication
- Image tag selection (default per environment)
- Registry pull instead of local build
- Better error handling
- Fixed outdated URLs (yourdomain.com → solar.64b.de)

### 4. Manual Build Script

**File Created**: `deployment/scripts/build-and-push.sh`

- Standalone script for manual image builds
- Support for custom tags
- Interactive confirmation
- Git commit SHA tagging

### 5. Environment Configuration

**Files Modified**:
- `.env.test.example` - Added IMAGE_TAG=test
- `.env.staging.example` - Added IMAGE_TAG=staging
- `.env.prod.example` - Added IMAGE_TAG=prod

**File Created**:
- `.env.image-tags.example` - Tag strategy documentation

### 6. Documentation

**File Created**: `docs/DOCKER-REGISTRY.md`
- Comprehensive registry guide
- Authentication instructions
- CI/CD documentation
- Troubleshooting guide
- Best practices

**Files Modified**:
- `README.md` - Added CI/CD section, updated deployment instructions
- `CLAUDE.md` - Added Docker registry and CI/CD sections
- `docs/DEPLOYMENT.md` - Updated URLs and references

### 7. Docker Optimization

**File Modified**: `.dockerignore`
- Comprehensive exclusion list
- Excludes deployment files, tests, docs
- Optimized for smaller image sizes

## Image Tagging Strategy

| Environment | Default Tag | Alternative Tags |
|-------------|-------------|------------------|
| Test | `test` | `sha-xxxxx`, branch names |
| Staging | `staging` | `v1.x.x-rc.1`, `sha-xxxxx` |
| Production | `prod` | `v1.2.3` (semantic versions) |

## Deployment Workflow

### Automated (CI/CD)

1. Push code to any branch → Image built automatically
2. Create git tag `v1.2.3` → Production image created
3. Images pushed to registry with multiple tags

### Manual Deployment

```bash
# Set credentials
export DOCKER_REGISTRY_USERNAME="your-username"
export DOCKER_REGISTRY_PASSWORD="your-password"

# Deploy with specific version
export IMAGE_TAG="v1.2.3"
deployment/scripts/deploy-prod.sh
```

## Required GitHub Secrets

Configure in repository settings:
- `DOCKER_REGISTRY_USERNAME`
- `DOCKER_REGISTRY_PASSWORD`

## Migration from Local Builds

**Before** (local builds on server):
```bash
docker-compose build
docker-compose up -d
```

**After** (registry pull):
```bash
docker login git.64b.de
docker-compose pull
docker-compose up -d
```

## Benefits

1. **Faster deployments**: Pull vs build (minutes → seconds)
2. **Consistent images**: Same artifact across all environments
3. **Version control**: Exact commit SHAs and semantic versions
4. **Easy rollback**: Pull any previous version
5. **CI/CD integration**: Automatic builds on every commit

## Testing Checklist

- [ ] GitHub Actions workflow builds successfully
- [ ] Docker registry authentication works
- [ ] Test environment deployment pulls correct image
- [ ] Staging environment deployment works
- [ ] Production deployment script has proper safeguards
- [ ] Image tags are created correctly
- [ ] Manual build script works
- [ ] Documentation is accurate and complete

## Next Steps

1. Configure GitHub Secrets in repository
2. Test CI/CD pipeline by pushing to a branch
3. Create first semantic version tag (`v1.0.0`)
4. Deploy to test environment to verify
5. Update deployment servers with registry credentials
6. Perform staged rollout (test → staging → prod)

## Rollback Plan

If issues occur:
1. Revert to previous branch: `git checkout main`
2. Deploy using old method (local builds)
3. Investigate and fix issues
4. Re-deploy when ready

## Additional Notes

- Collector image (`git.64b.de/bjoern/inverter-collector:latest`) is unchanged (separate deployment)
- Development workflow (`docker-compose.yml`) unchanged - still uses local builds
- All deployment scripts maintain backward compatibility
- No database schema changes - safe to deploy

## Documentation References

- [Docker Registry Guide](docs/DOCKER-REGISTRY.md) - Complete registry documentation
- [Deployment Guide](docs/DEPLOYMENT.md) - Deployment procedures
- [CLAUDE.md](CLAUDE.md) - Development guide with CI/CD info
- [README.md](README.md) - Updated with registry information

---

**Created**: October 31, 2025
**Author**: Claude Code
**Branch**: `feat/docker-registry-deployment`
