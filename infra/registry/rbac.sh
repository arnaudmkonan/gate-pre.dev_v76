#!/bin/bash
set -e

# Registry RBAC Management Script
# Configure role-based access control and token management for private container registry
# Usage: ./rbac.sh <command> [options]

REGISTRY_URL="${REGISTRY_URL:-registry.railway.app}"
REGISTRY_ADMIN_USER="${REGISTRY_ADMIN_USER:-admin}"
REGISTRY_ADMIN_PASSWORD="${REGISTRY_ADMIN_PASSWORD:-}"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions

log_info() {
  echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

create_user() {
  local username=$1
  local password=$2
  local permissions=${3:-pull}

  log_info "Creating user: $username"

  # Hash password using bcrypt
  local password_hash=$(htpasswd -bnBC 10 "" "$password" | tr -d ':\n' | sed 's/\$2y/\$2a/')

  # Create htpasswd file entry
  echo "$username:$password_hash" >> /etc/docker/registry/htpasswd

  log_info "User created successfully"
  echo "Username: $username"
  echo "Password: $password"
  echo "Permissions: $permissions"
}

create_token() {
  local service=$1
  local ttl=${2:-7d}
  local permissions=${3:-pull}

  log_info "Creating token for service: $service"
  log_info "TTL: $ttl, Permissions: $permissions"

  # Generate random token
  local token=$(openssl rand -base64 32 | tr -d '\n')

  # Store token metadata
  local token_file="/var/lib/registry/tokens/$service-$(date +%Y%m%d-%H%M%S).token"
  mkdir -p /var/lib/registry/tokens

  cat > "$token_file" <<EOF
token=$token
service=$service
permissions=$permissions
created=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
expires=$(date -u -d "+$ttl" +'%Y-%m-%dT%H:%M:%SZ')
EOF

  log_info "Token created successfully"
  echo "Token: $token"
  echo "Service: $service"
  echo "Permissions: $permissions"
  echo "TTL: $ttl"
  echo "Storage: $token_file"
}

revoke_token() {
  local token_id=$1

  log_info "Revoking token: $token_id"

  local token_file="/var/lib/registry/tokens/$token_id.token"

  if [ ! -f "$token_file" ]; then
    log_error "Token not found: $token_id"
    return 1
  fi

  # Mark token as revoked
  echo "revoked=true" >> "$token_file"
  log_info "Token revoked successfully"
}

list_users() {
  log_info "Listing registry users"

  if [ -f /etc/docker/registry/htpasswd ]; then
    awk -F: '{print $1}' /etc/docker/registry/htpasswd
  else
    log_warn "No users configured"
  fi
}

list_tokens() {
  log_info "Listing active tokens"

  local tokens_dir="/var/lib/registry/tokens"
  if [ ! -d "$tokens_dir" ]; then
    log_warn "No tokens found"
    return
  fi

  for token_file in "$tokens_dir"/*.token; do
    if [ -f "$token_file" ]; then
      local service=$(grep '^service=' "$token_file" | cut -d'=' -f2)
      local expires=$(grep '^expires=' "$token_file" | cut -d'=' -f2)
      local revoked=$(grep '^revoked=' "$token_file" | cut -d'=' -f2)

      if [ -z "$revoked" ] || [ "$revoked" != "true" ]; then
        echo "Service: $service, Expires: $expires"
      fi
    fi
  done
}

setup_rbac() {
  log_info "Setting up RBAC roles"

  # Create admin user
  create_user "admin" "$REGISTRY_ADMIN_PASSWORD" "admin"

  # Create service accounts
  create_user "ci-bot" "$(openssl rand -base64 32)" "admin"
  create_user "staging-reader" "$(openssl rand -base64 32)" "pull"
  create_user "prod-reader" "$(openssl rand -base64 32)" "pull"

  log_info "RBAC setup completed"
}

cleanup_expired_tokens() {
  log_info "Cleaning up expired tokens"

  local tokens_dir="/var/lib/registry/tokens"
  if [ ! -d "$tokens_dir" ]; then
    return
  fi

  local now=$(date +%s)
  local count=0

  for token_file in "$tokens_dir"/*.token; do
    if [ -f "$token_file" ]; then
      local expires=$(grep '^expires=' "$token_file" | cut -d'=' -f2)
      local expires_timestamp=$(date -d "$expires" +%s 2>/dev/null || echo 0)

      if [ "$expires_timestamp" -lt "$now" ]; then
        rm "$token_file"
        count=$((count + 1))
      fi
    fi
  done

  log_info "Cleaned up $count expired tokens"
}

rotate_credentials() {
  log_info "Rotating registry credentials"

  # Generate new admin password
  local new_admin_pass=$(openssl rand -base64 32)

  log_warn "New admin password: $new_admin_pass"
  log_warn "Store this securely and update REGISTRY_ADMIN_PASSWORD"

  # Update htpasswd
  htpasswd -bBC 10 /etc/docker/registry/htpasswd "admin" "$new_admin_pass"

  log_info "Admin credentials rotated"

  # Generate new service account tokens
  log_info "Generating new service account tokens"
  create_token "ci-bot" "365d" "admin"
  create_token "staging-reader" "90d" "pull"
  create_token "prod-reader" "90d" "pull"

  log_info "Credentials rotated successfully"
}

validate_auth() {
  local username=$1
  local password=$2

  log_info "Validating credentials for user: $username"

  # Test docker login
  if echo "$password" | docker login -u "$username" --password-stdin "$REGISTRY_URL"; then
    log_info "Authentication successful"
    return 0
  else
    log_error "Authentication failed"
    return 1
  fi
}

print_usage() {
  cat <<EOF
Registry RBAC Management Script

Usage: $0 <command> [options]

Commands:
  create-user <username> <password> [permissions]
    Create a new registry user
    Example: $0 create-user ci-bot "password123" admin

  create-token <service> [ttl] [permissions]
    Create a time-limited token for service
    Example: $0 create-token ci-bot 30d admin

  revoke-token <token-id>
    Revoke a token
    Example: $0 revoke-token ci-bot-20240120-120000

  list-users
    List all registry users

  list-tokens
    List all active tokens

  setup-rbac
    Setup initial RBAC roles and service accounts

  cleanup-expired
    Remove expired tokens

  rotate-credentials
    Rotate all credentials (admin + service accounts)

  validate-auth <username> <password>
    Validate user credentials

  help
    Show this help message

Environment Variables:
  REGISTRY_URL              Registry URL (default: registry.railway.app)
  REGISTRY_ADMIN_USER       Admin username (default: admin)
  REGISTRY_ADMIN_PASSWORD   Admin password (required for some commands)

Examples:
  # Create CI bot with admin permissions
  $0 create-user ci-bot "strong-password" admin

  # Create a 7-day token
  $0 create-token staging-deploy 7d pull

  # List all users
  $0 list-users

  # Rotate all credentials
  REGISTRY_ADMIN_PASSWORD="old-pass" $0 rotate-credentials
EOF
}

# Main

if [ $# -eq 0 ]; then
  print_usage
  exit 1
fi

case "$1" in
  create-user)
    if [ $# -lt 3 ]; then
      log_error "Usage: $0 create-user <username> <password> [permissions]"
      exit 1
    fi
    create_user "$2" "$3" "${4:-pull}"
    ;;
  create-token)
    if [ $# -lt 2 ]; then
      log_error "Usage: $0 create-token <service> [ttl] [permissions]"
      exit 1
    fi
    create_token "$2" "${3:-7d}" "${4:-pull}"
    ;;
  revoke-token)
    if [ $# -lt 2 ]; then
      log_error "Usage: $0 revoke-token <token-id>"
      exit 1
    fi
    revoke_token "$2"
    ;;
  list-users)
    list_users
    ;;
  list-tokens)
    list_tokens
    ;;
  setup-rbac)
    if [ -z "$REGISTRY_ADMIN_PASSWORD" ]; then
      log_error "REGISTRY_ADMIN_PASSWORD environment variable required"
      exit 1
    fi
    setup_rbac
    ;;
  cleanup-expired)
    cleanup_expired_tokens
    ;;
  rotate-credentials)
    if [ -z "$REGISTRY_ADMIN_PASSWORD" ]; then
      log_error "REGISTRY_ADMIN_PASSWORD environment variable required"
      exit 1
    fi
    rotate_credentials
    ;;
  validate-auth)
    if [ $# -lt 3 ]; then
      log_error "Usage: $0 validate-auth <username> <password>"
      exit 1
    fi
    validate_auth "$2" "$3"
    ;;
  help)
    print_usage
    ;;
  *)
    log_error "Unknown command: $1"
    print_usage
    exit 1
    ;;
esac
