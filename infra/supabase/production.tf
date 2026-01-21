# Supabase Production Infrastructure as Code
# Provisions production Supabase project with database, auth, and storage

terraform {
  required_providers {
    supabase = {
      source = "supabase/supabase"
      version = "~> 1.0"
    }
  }

  backend "s3" {
    bucket         = "doc-ingestion-terraform-state"
    key            = "supabase/production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-lock"
  }
}

provider "supabase" {
  access_token = var.supabase_access_token
}

# Variables
variable "supabase_access_token" {
  description = "Supabase API access token"
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Supabase project name"
  type        = string
  default     = "doc-ingestion-prod"
}

variable "region" {
  description = "Supabase region"
  type        = string
  default     = "us-east-1"
}

variable "organization_id" {
  description = "Supabase organization ID"
  type        = string
}

# Production Supabase Project
resource "supabase_project" "production" {
  name             = var.project_name
  organization_id  = var.organization_id
  region           = var.region
  database_version = "14"

  tags = {
    environment = var.environment
    terraform   = "true"
  }
}

# Database Configuration
resource "supabase_database" "production" {
  project_id = supabase_project.production.id
  name       = "doc_ingestion"

  # Enable extensions
  extensions = [
    "uuid-ossp",
    "pgvector",
    "pg_trgm",
    "plpgsql"
  ]

  # Database parameters for production
  settings = {
    # Performance
    shared_buffers                = "262144"    # 2GB
    effective_cache_size          = "2097152"   # 16GB
    maintenance_work_mem          = "524288"    # 512MB
    work_mem                      = "4096"      # 4MB

    # Connections
    max_connections              = 100
    max_prepared_transactions    = 200

    # Logging
    log_statement                = "mod"
    log_duration                 = true
    log_min_duration_statement   = 1000
    log_connections              = true
    log_disconnections           = true

    # Replication
    wal_level                    = "replica"
    max_wal_senders              = 10
  }

  # Encryption at rest (enabled by default in production)
  encryption_at_rest = true
  ssl_enforcement    = true

  tags = {
    environment = var.environment
  }
}

# Authentication Configuration
resource "supabase_auth_config" "production" {
  project_id = supabase_project.production.id

  jwt_secret                    = var.jwt_secret
  jwt_expiry_seconds            = 3600
  refresh_token_expiry_seconds  = 604800  # 7 days

  # Email authentication
  email_auth_enabled = true
  email_confirmations_required = true
  email_verification_ttl_seconds = 86400  # 24 hours

  # Password policy
  password_min_length = 8
  password_require_uppercase = true
  password_require_numbers = true
  password_require_special_characters = true

  # Session settings
  session_timeout_seconds = 3600
  single_session_per_user = false

  tags = {
    environment = var.environment
  }
}

# Storage Configuration
resource "supabase_storage_bucket" "raw_files" {
  project_id = supabase_project.production.id
  name       = "raw-files"
  is_public  = false

  file_size_limit = 104857600  # 100MB in bytes

  cors_enabled = true
  cors_allowed_origins = [
    "https://app.example.com",
    "https://api.example.com"
  ]

  lifecycle_rules = {
    enabled = true
    expire_days = 30  # Expire unverified uploads after 30 days
  }

  tags = {
    environment = var.environment
    purpose     = "raw-file-storage"
  }
}

resource "supabase_storage_bucket" "silver_data" {
  project_id = supabase_project.production.id
  name       = "silver-data"
  is_public  = false

  file_size_limit = 104857600  # 100MB

  cors_enabled = true
  cors_allowed_origins = [
    "https://app.example.com",
    "https://api.example.com"
  ]

  tags = {
    environment = var.environment
    purpose     = "normalized-data-storage"
  }
}

resource "supabase_storage_bucket" "backups" {
  project_id = supabase_project.production.id
  name       = "backups"
  is_public  = false

  file_size_limit = 1099511627776  # 1TB

  cors_enabled = true
  cors_allowed_origins = [
    "https://api.example.com"
  ]

  lifecycle_rules = {
    enabled = true
    expire_days = 90  # Retain backups for 90 days
  }

  tags = {
    environment = var.environment
    purpose     = "database-and-storage-backups"
  }
}

# Monitoring and Alerts
resource "supabase_monitoring" "production" {
  project_id = supabase_project.production.id

  # Database monitoring
  slow_query_threshold = 1000  # milliseconds

  # Alerts
  alerts = {
    database_size_threshold_gb = 10
    connection_count_threshold = 80
    disk_io_threshold_percent = 90
  }

  tags = {
    environment = var.environment
  }
}

# Backups Configuration
resource "supabase_backup" "production" {
  project_id = supabase_project.production.id

  # Automated daily backups
  schedule = "daily"
  time     = "02:00"  # 2 AM UTC

  # Retention policy
  retention_days = 30

  # Backup location
  storage_location = "us-east-1"

  # Enable incremental backups
  incremental_enabled = true

  # Point-in-time recovery (PITR)
  pitr_enabled = true
  pitr_days    = 7

  tags = {
    environment = var.environment
  }
}

# Outputs
output "project_id" {
  description = "Supabase project ID"
  value       = supabase_project.production.id
}

output "project_url" {
  description = "Supabase project URL"
  value       = supabase_project.production.project_url
}

output "database_host" {
  description = "Database host"
  value       = supabase_project.production.database_host
}

output "database_port" {
  description = "Database port"
  value       = supabase_project.production.database_port
}

output "api_url" {
  description = "Supabase API URL"
  value       = supabase_project.production.api_url
}

output "anon_key" {
  description = "Supabase anonymous key"
  value       = supabase_project.production.anon_key
  sensitive   = true
}

output "service_role_key" {
  description = "Supabase service role key"
  value       = supabase_project.production.service_role_key
  sensitive   = true
}

output "storage_buckets" {
  description = "Storage bucket names"
  value = {
    raw_files  = supabase_storage_bucket.raw_files.name
    silver_data = supabase_storage_bucket.silver_data.name
    backups    = supabase_storage_bucket.backups.name
  }
}
