# GATE Platform — Database Migration Guide

## Overview

GATE uses **Alembic** for database schema migrations. All schema changes MUST be made through Alembic migrations, never through direct SQL or `create_all()`.

## Quick Reference

```bash
# Check if database matches models
cd services/api && alembic check

# Generate a new migration from model changes
cd services/api && alembic revision --autogenerate -m "description_of_change"

# Apply all pending migrations
cd services/api && alembic upgrade head

# Rollback one migration
cd services/api && alembic downgrade -1

# View current migration version
cd services/api && alembic current

# View migration history
cd services/api && alembic history
```

## Workflow for Schema Changes

### 1. Modify the Model

Edit the SQLAlchemy model in `services/api/app/models/`:

```python
# Example: Adding a new column to Entry
class Entry(Base):
    __tablename__ = "entries"
    
    # ... existing columns ...
    priority = Column(String, nullable=True)  # NEW COLUMN
```

### 2. Generate the Migration

```bash
cd services/api
alembic revision --autogenerate -m "add_priority_to_entries"
```

This creates a new file in `alembic/versions/` with `upgrade()` and `downgrade()` functions.

### 3. Review the Migration

**Always review auto-generated migrations.** Alembic can miss:
- Default values for existing rows
- Data migrations (transforming data during schema change)
- Index optimizations

### 4. Apply the Migration

```bash
# Local development
cd services/api && alembic upgrade head

# Production (via instance)
cd instances/<customer-id>
docker compose exec api alembic upgrade head
```

### 5. Commit

Commit both the model change and the migration file together.

## Migration Conventions

| Convention | Rule |
|-----------|------|
| **Naming** | `alembic revision --autogenerate -m "verb_noun_detail"` (e.g., `add_priority_to_entries`) |
| **One migration per change** | Don't batch unrelated schema changes |
| **Data migrations** | Use a separate migration for data transformation |
| **Downgrade** | Always implement `downgrade()` so rollback is possible |
| **Testing** | Test upgrade AND downgrade before merging |

## Instance Provisioning

New customer instances use `alembic upgrade head` in `init.sh` to create all tables from migrations (not `create_all()`).

## Existing Migrations

| Version | Description | Date |
|---------|------------|------|
| `b663ab8dfc32` | Add silver and gold data layers | 2026-01-23 |
| `c8f7a9b2d1e4` | Add reference data tables | 2026-01-23 |
| `d9e8f7c6b5a4` | Add ACE entries table | 2026-01-23 |
| `e1f2g3h4i5j6` | Add document keys table | 2026-01-24 |
| `f2g3h4i5j6k7` | Add shipment documents table | 2026-01-24 |
| `g3h4i5j6k7l8` | Add entry source type | 2026-01-28 |

## Troubleshooting

### "Target database is not up to date"
```bash
alembic stamp head  # Mark current DB state as latest
```

### "Can't locate revision"
Migration files might be missing. Check `alembic/versions/` directory.

### "Table already exists" on fresh database
The baseline migration should use `checkfirst=True`:
```python
def upgrade():
    op.create_table('my_table', ..., if_not_exists=True)
```
