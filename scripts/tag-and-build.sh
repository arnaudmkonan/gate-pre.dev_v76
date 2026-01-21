#!/bin/bash
set -e

# Script to generate semantic version + git SHA tags for Docker images
# Usage: ./scripts/tag-and-build.sh [api|web] [registry-url] [registry-username] [registry-password]

SERVICE=${1:-api}
REGISTRY=${2:-localhost:5000}
REGISTRY_USERNAME=${3:-}
REGISTRY_PASSWORD=${4:-}

# Get semantic version from git tags
VERSION=$(git describe --tags --always --dirty 2>/dev/null | sed 's/^v//' || echo "0.0.0")
SHORT_SHA=$(git rev-parse --short HEAD)
FULL_SHA=$(git rev-parse HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

# Generate tag
TAG="$VERSION-$SHORT_SHA"
SEMVER_TAG="v$VERSION"
COMMIT_TAG="commit-$SHORT_SHA"

echo "========================================"
echo "Docker Image Build & Tag"
echo "========================================"
echo "Service:        $SERVICE"
echo "Registry:       $REGISTRY"
echo "Version:        $VERSION"
echo "Git SHA:        $SHORT_SHA"
echo "Full SHA:       $FULL_SHA"
echo "Branch:         $BRANCH"
echo "Build Date:     $BUILD_DATE"
echo "Image Tags:     $TAG, $SEMVER_TAG, latest, $COMMIT_TAG"
echo "========================================"

# Determine dockerfile path
case $SERVICE in
  api)
    DOCKERFILE="services/api/Dockerfile"
    CONTEXT="services/api"
    IMAGE_NAME="doc-ingestion-api"
    ;;
  web)
    DOCKERFILE="apps/web/Dockerfile"
    CONTEXT="apps/web"
    IMAGE_NAME="doc-ingestion-web"
    ;;
  *)
    echo "Invalid service: $SERVICE. Use 'api' or 'web'"
    exit 1
    ;;
esac

# Check dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
  echo "Dockerfile not found: $DOCKERFILE"
  exit 1
fi

# Build image with tags
echo "Building Docker image..."
docker build \
  --tag "$REGISTRY/$IMAGE_NAME:$TAG" \
  --tag "$REGISTRY/$IMAGE_NAME:$SEMVER_TAG" \
  --tag "$REGISTRY/$IMAGE_NAME:latest" \
  --tag "$REGISTRY/$IMAGE_NAME:$COMMIT_TAG" \
  --build-arg "VERSION=$VERSION" \
  --build-arg "BUILD_DATE=$BUILD_DATE" \
  --build-arg "VCS_REF=$FULL_SHA" \
  --build-arg "VCS_BRANCH=$BRANCH" \
  --label "org.opencontainers.image.version=$VERSION" \
  --label "org.opencontainers.image.created=$BUILD_DATE" \
  --label "org.opencontainers.image.revision=$FULL_SHA" \
  --label "org.opencontainers.image.title=$IMAGE_NAME" \
  --file "$DOCKERFILE" \
  "$CONTEXT"

echo "✓ Image built successfully"
echo "Tags:"
echo "  - $REGISTRY/$IMAGE_NAME:$TAG"
echo "  - $REGISTRY/$IMAGE_NAME:$SEMVER_TAG"
echo "  - $REGISTRY/$IMAGE_NAME:$COMMIT_TAG"
echo "  - $REGISTRY/$IMAGE_NAME:latest"

# Login to registry if credentials provided
if [ -n "$REGISTRY_USERNAME" ] && [ -n "$REGISTRY_PASSWORD" ]; then
  echo ""
  echo "Logging in to registry..."
  echo "$REGISTRY_PASSWORD" | docker login -u "$REGISTRY_USERNAME" --password-stdin "$REGISTRY"

  echo "Pushing images to registry..."
  docker push "$REGISTRY/$IMAGE_NAME:$TAG"
  docker push "$REGISTRY/$IMAGE_NAME:$SEMVER_TAG"
  docker push "$REGISTRY/$IMAGE_NAME:$COMMIT_TAG"
  docker push "$REGISTRY/$IMAGE_NAME:latest"

  echo "✓ Images pushed successfully"

  # Logout
  docker logout "$REGISTRY"
else
  echo ""
  echo "Registry credentials not provided. Skipping push."
  echo "To push images, run:"
  echo "  docker login $REGISTRY"
  echo "  docker push $REGISTRY/$IMAGE_NAME:$TAG"
fi

echo ""
echo "Build completed successfully!"
