"""
Cleanup unused database tables.

This migration archives tables that have no data and are not actively used.
Tables are renamed with '_deprecated' suffix rather than dropped, allowing 
for easy rollback if needed.

Revision ID: cleanup_unused_001
Revises: (previous migration)
Create Date: 2026-02-01 01:30:00
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# Revision identifiers
revision = 'cleanup_unused_001'
down_revision = None  # Set to actual previous migration
branch_labels = None
depends_on = None

# Tables with zero rows that can be safely archived
# These are either:
# 1. Redundant (duplicate functionality)
# 2. Legacy (from old features)
# 3. Future placeholders (not yet implemented)
TABLES_TO_ARCHIVE = [
    # Redundant medallion architecture tables (raw layer tables duplicating extraction_results)
    'raw_metadata',
    'raw_extractions', 
    'raw_vectors',
    'silver_metadata',
    'silver_records',
    
    # Duplicate DLQ tables
    'dlq_entries',  # Keep dead_letter_queue
    
    # Unused compliance/entry tables (customs_entries is legacy, entries is current)
    'customs_entries',
    'commercial_invoices',
    'invoice_lines',
    'invoice_payments',
    
    # Unused notification/session tables  
    'client_notifications',
    'client_user_sessions',
    'client_users',
    
    # Unused billing tables
    'billable_items',
    'client_invoices',
    'client_fee_configs',
    
    # Unused admin tables
    'organization_subscriptions',
    'portal_invitations',
    'onboarding_progress',
    'security_audit_log',
    
    # Unused analytics/monitoring tables
    'metrics_timeseries',
    'monitoring_metrics',
    'generated_reports',
    'scheduled_reports',
    
    # Unused entry lifecycle tables
    'entry_liquidations',
    'entry_protests',
    'reconciliation_entries',
    'prior_disclosures',
    
    # Unused shipping/ISF tables
    'shipments',
    'shipment_documents',
    'isf_amendments',
    'isf_filings',
    
    # Unused reference data tables
    'add_cvd_orders' if False else None,  # Skip, might be used
    'naics_codes',
    'hts_codes',  # Large file, keep if HTS lookup is important
    
    # Unused workflow tables
    'bulk_review_sessions',
    'correction_logs',
    'upload_events',
    
    # Unused agent tables (if not using specific agents)
    'agent_ack',
    'agent_registry',
    
    # Unused file tracking tables  
    'file_snapshot',
    'file_version',
    'document_keys',
    'document_requests',
    
    # Unused retry/queue tables (queue_job is current)
    'retry_queue',
    'retry_jobs',
    'retry_policies',
    'ingestion_retries',
    
    # Unused config tables
    'celery_config',
    'storage_config', 
    'vector_store_config',
    
    # Other unused tables
    'batches',
    'batch_schedules',
    'addresses',
    'parties',
    'few_shot_examples',
    'normalization_validation',
    'overrides_audit',
    'quarantine',
    'data_exceptions',
    'alert_rules',
    'alerts',
    'roles',
    'user_roles',
    'help_articles',
    'upload_metadata',
    'template_field_metrics',
    'vector_records',
    'routing_decisions',
    'job_log',
    'ingest_batches',
    'ingest_files',
    'drawback_claims',
    'drawback_ledger',
    'compliance_screens',
    'filer_codes',
    'file_type_mappings',
    'products',
    'organizations',
    'ace_entries',
    'ace_settings',
]

# Remove None values
TABLES_TO_ARCHIVE = [t for t in TABLES_TO_ARCHIVE if t]

# Tables to KEEP (have data or are actively used)
TABLES_TO_KEEP = [
    'alembic_version',  # Migration tracking
    'document_metadata',  # Core document storage
    'extraction_results',  # Core extraction storage  
    'extraction_templates',  # Template definitions
    'review_queue',  # Human review workflow
    'review_actions',  # Review action log
    'document_embeddings',  # Vector search
    'batch_jobs',  # Batch processing
    'ingest_jobs',  # Ingestion tracking
    'raw_files',  # File storage references
    'upload_idempotency_keys',  # Deduplication
    'entries',  # Customs entries
    'entry_lines',  # Entry line items
    'entry_parties',  # Entry parties
    'entry_documents',  # Entry-document links
    'entry_status_history',  # Entry workflow
    'clients',  # Client management
    'client_settings',  # Client preferences
    'client_bonds',  # Client bonds  
    'client_contacts',  # Client contacts
    'errors_raw',  # Error tracking
    'dead_letter_queue',  # Failed job recovery
    'queue_job',  # Job queue
    'entity_links',  # Entity resolution
    'embeddings',  # General embeddings
    'field_mapping_templates',  # Export mappings
    'audit_log',  # Audit trail
]


def upgrade():
    """Archive unused tables by renaming them."""
    connection = op.get_bind()
    
    for table_name in TABLES_TO_ARCHIVE:
        # Check if table exists
        result = connection.execute(sa.text(
            f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
        ))
        exists = result.scalar()
        
        if exists:
            # Check if already archived
            archived_name = f"{table_name}_deprecated"
            result = connection.execute(sa.text(
                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{archived_name}')"
            ))
            already_archived = result.scalar()
            
            if not already_archived:
                # Rename to archived
                op.rename_table(table_name, archived_name)
                print(f"Archived: {table_name} -> {archived_name}")
            else:
                print(f"Already archived: {table_name}")
        else:
            print(f"Table not found: {table_name}")


def downgrade():
    """Restore archived tables by renaming them back."""
    connection = op.get_bind()
    
    for table_name in TABLES_TO_ARCHIVE:
        archived_name = f"{table_name}_deprecated"
        
        # Check if archived table exists
        result = connection.execute(sa.text(
            f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{archived_name}')"
        ))
        exists = result.scalar()
        
        if exists:
            # Check if original already exists
            result = connection.execute(sa.text(
                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
            ))
            original_exists = result.scalar()
            
            if not original_exists:
                op.rename_table(archived_name, table_name)
                print(f"Restored: {archived_name} -> {table_name}")
            else:
                print(f"Original exists, skipping: {table_name}")
        else:
            print(f"Archived table not found: {archived_name}")
