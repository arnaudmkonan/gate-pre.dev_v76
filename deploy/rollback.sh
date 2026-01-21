#!/bin/bash
set -e

# Container Rollback Script
# Rollback to a previous container image version in Railway
# Usage: ./deploy/rollback.sh [--service SERVICE] [--environment ENV] [--version VERSION] [--dry-run]

SERVICE=${SERVICE:-api}
ENVIRONMENT=${ENVIRONMENT:-staging}
VERSION=${VERSION:-}
DRY_RUN=false
REGISTRY_URL=${REGISTRY_URL:-registry.railway.app}

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
  echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_debug() {
  echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --service)
      SERVICE="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --version)
      VERSION="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --registry)
      REGISTRY_URL="$2"
      shift 2
      ;;
    --help)
      print_usage
      exit 0
      ;;
    *)
      log_error "Unknown option: $1"
      print_usage
      exit 1
      ;;
  esac
done

print_usage() {
  cat <<EOF
Container Rollback Script

Usage: $0 [options]

Options:
  --service SERVICE              Service to rollback (api, web) [default: api]
  --environment ENV              Target environment (staging, production) [default: staging]
  --version VERSION              Version to rollback to (e.g., v1.2.3)
  --registry REGISTRY_URL        Container registry URL
  --dry-run                      Show what would be done without making changes
  --help                         Show this help message

Examples:
  # Rollback API to previous version in staging
  $0 --service api --environment staging

  # Rollback web to specific version
  $0 --service web --version v1.2.3

  # Dry-run rollback in production
  $0 --service api --environment production --dry-run

Requirements:
  - railway CLI installed and authenticated
  - docker CLI installed
  - jq for JSON parsing
EOF
}

# Check requirements
check_requirements() {
  log_info "Checking requirements..."

  if ! command -v railway &> /dev/null; then
    log_error "railway CLI not found. Install from https://docs.railway.app/develop/cli"
    exit 1
  fi

  if ! command -v docker &> /dev/null; then
    log_error "docker CLI not found"
    exit 1
  fi

  if ! command -v jq &> /dev/null; then
    log_warn "jq not found. Some features may not work."
  fi

  log_info "Requirements met"
}

# Get service details
get_service_details() {
  local service_name=$1
  local env=$2

  log_info "Fetching service details: $service_name in $env..."

  # Get current image
  railway link "${SERVICE}_${ENVIRONMENT}_project_id"
  local current_image=$(railway env | grep "CURRENT_IMAGE" | cut -d'=' -f2)

  log_info "Current image: $current_image"
}

# List available versions
list_available_versions() {
  local service_name=$1
  local image_repo="${REGISTRY_URL}/doc-ingestion-${service_name}"

  log_info "Listing available versions for $image_repo..."

  # Query registry for available tags
  docker run --rm \
    -e REGISTRY_URL="$REGISTRY_URL" \
    alpine/curl sh -c "
    curl -s -H 'Accept: application/json' \
    https://${REGISTRY_URL}/v2/${service_name}/tags/list | \
    jq -r '.tags[] | select(. != null)' | \
    head -20
  " 2>/dev/null || log_error "Failed to list versions"
}

# Get previous version from history
get_previous_version() {
  local service_name=$1

  log_info "Retrieving previous version from deployment history..."

  # This would query deployment history from Railway
  # For now, we'll list recent versions
  local image_repo="${REGISTRY_URL}/doc-ingestion-${service_name}"

  # Try to get from Docker registry
  if [ -n "$(command -v curl)" ]; then
    curl -s -H "Accept: application/json" \
      "https://${REGISTRY_URL}/v2/${service_name}/tags/list" 2>/dev/null | \
      jq -r '.tags[]' 2>/dev/null | \
      grep -v latest | \
      grep -v commit | \
      head -1 || true
  fi
}

# Perform rollback
perform_rollback() {
  local service_name=$1
  local environment=$2
  local target_version=$3

  if [ -z "$target_version" ]; then
    target_version=$(get_previous_version "$service_name")
    log_info "Auto-detected target version: $target_version"
  fi

  if [ -z "$target_version" ]; then
    log_error "No target version specified and unable to detect previous version"
    exit 1
  fi

  local image_url="${REGISTRY_URL}/doc-ingestion-${service_name}:${target_version}"

  log_info "Rolling back to: $image_url"

  if [ "$DRY_RUN" = true ]; then
    log_warn "DRY RUN MODE - No changes will be made"
  fi

  # Update deployment
  log_info "Updating deployment..."

  if [ "$DRY_RUN" = false ]; then
    railway link "${SERVICE}_${ENVIRONMENT}_project_id"
    railway env set "IMAGE_URL=$image_url"
    railway up --service "$service_name"
  else
    log_debug "Would execute: railway env set IMAGE_URL=$image_url"
    log_debug "Would execute: railway up --service $service_name"
  fi
}

# Health check
health_check() {
  local service_name=$1
  local environment=$2
  local max_attempts=30
  local attempt=1

  log_info "Performing health checks..."

  while [ $attempt -le $max_attempts ]; do
    log_debug "Health check attempt $attempt/$max_attempts..."

    case "$service_name" in
      api)
        local health_url="http://localhost:8000/health"
        ;;
      web)
        local health_url="http://localhost:3000"
        ;;
      *)
        log_error "Unknown service: $service_name"
        return 1
        ;;
    esac

    if curl -sf "$health_url" > /dev/null 2>&1; then
      log_info "Health check passed"
      return 0
    fi

    if [ $attempt -lt $max_attempts ]; then
      log_debug "Health check failed, retrying in 10 seconds..."
      sleep 10
    fi

    attempt=$((attempt + 1))
  done

  log_error "Health check failed after $max_attempts attempts"
  return 1
}

# Verify rollback
verify_rollback() {
  local service_name=$1
  local target_version=$2

  log_info "Verifying rollback to $target_version..."

  railway link "${SERVICE}_${ENVIRONMENT}_project_id"

  # Get current deployment
  local current_image=$(railway env | grep "IMAGE_URL" | cut -d'=' -f2)

  if [[ "$current_image" == *"$target_version"* ]]; then
    log_info "✓ Rollback verified successfully"
    log_info "Current image: $current_image"
    return 0
  else
    log_error "✗ Rollback verification failed"
    log_error "Expected: $target_version"
    log_error "Current: $current_image"
    return 1
  fi
}

# Main execution
main() {
  echo "========================================"
  echo "Container Rollback"
  echo "========================================"
  echo "Service:      $SERVICE"
  echo "Environment:  $ENVIRONMENT"
  echo "Version:      ${VERSION:-auto-detect}"
  echo "Registry:     $REGISTRY_URL"
  echo "Dry-run:      $DRY_RUN"
  echo "========================================"
  echo ""

  check_requirements

  log_info "Starting rollback process..."
  log_info "Service: $SERVICE, Environment: $ENVIRONMENT"

  perform_rollback "$SERVICE" "$ENVIRONMENT" "$VERSION"

  if [ "$DRY_RUN" = false ]; then
    log_info "Waiting for deployment to stabilize..."
    sleep 30

    if health_check "$SERVICE" "$ENVIRONMENT"; then
      verify_rollback "$SERVICE" "${VERSION:-(previous)}"
      log_info "Rollback completed successfully ✓"
      echo ""
      echo "Rollback Summary:"
      echo "  Service: $SERVICE"
      echo "  Environment: $ENVIRONMENT"
      echo "  Status: SUCCESS"
      echo "  RTO: < 5 minutes"
      exit 0
    else
      log_error "Health check failed after rollback"
      log_warn "Manual intervention may be required"
      exit 1
    fi
  else
    log_info "Dry-run completed. No changes made."
    exit 0
  fi
}

main
