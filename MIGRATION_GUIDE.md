# Database Migration Guide with Alembic

## Overview

This guide explains how to use Alembic for safe, production-ready database migrations that preserve data during schema changes.

## Why Alembic?

**Problem**: Adding/removing database columns with SQLAlchemy requires deleting the database, causing data loss.

**Solution**: Alembic tracks schema changes and applies them incrementally without data loss.

---

## Initial Setup (One-Time)

### 1. Install and Initialize Alembic

```bash
cd itimeline-backend
python setup_alembic.py
```

This will:
- Install Alembic package
- Create `alembic/` directory
- Create `alembic.ini` configuration file

### 2. Configure Alembic

Edit `alembic/env.py` to connect to your database:

```python
# Find this line (around line 7):
from app import db
from models import *  # Import all your models

# Find this line (around line 21):
target_metadata = db.metadata  # Use your SQLAlchemy metadata
```

Edit `alembic.ini` to set your database URL:

```ini
# Find this line (around line 63):
sqlalchemy.url = sqlite:///instance/itimeline.db
```

---

## Creating Migrations

### Automatic Migration (Recommended)

Alembic can auto-detect schema changes:

```bash
# After changing models in app.py
alembic revision --autogenerate -m "Add requires_approval to Timeline"
```

This creates a migration file in `alembic/versions/` with:
- **Upgrade**: SQL to apply changes
- **Downgrade**: SQL to revert changes

### Manual Migration (Advanced)

For complex changes:

```bash
alembic revision -m "Custom migration description"
```

Then edit the generated file in `alembic/versions/`.

---

## Applying Migrations

### Upgrade to Latest

```bash
alembic upgrade head
```

### Upgrade One Step

```bash
alembic upgrade +1
```

### Downgrade One Step

```bash
alembic downgrade -1
```

### View Migration History

```bash
alembic history
alembic current
```

---

## Example: Adding `requires_approval` Field

### Step 1: Modify Model

```python
# app.py
class Timeline(db.Model):
    # ... existing fields ...
    requires_approval = db.Column(db.Boolean, default=False, nullable=False)
```

### Step 2: Generate Migration

```bash
alembic revision --autogenerate -m "Add requires_approval to Timeline"
```

### Step 3: Review Migration

Check `alembic/versions/xxxx_add_requires_approval_to_timeline.py`:

```python
def upgrade():
    op.add_column('timeline', sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('timeline', 'requires_approval')
```

### Step 4: Apply Migration

```bash
alembic upgrade head
```

**Result**: Column added, all existing data preserved! ✅

---

## Best Practices

### 1. Always Review Auto-Generated Migrations

Alembic is smart but not perfect. Always check the generated migration file before applying.

### 2. Test Migrations Locally First

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply to local database
alembic upgrade head

# Test your application
# If issues, rollback:
alembic downgrade -1
```

### 3. Commit Migrations to Git

```bash
git add alembic/versions/xxxx_migration_name.py
git commit -m "Add migration: description"
```

### 4. Never Edit Applied Migrations

Once a migration is applied (especially in production), never edit it. Create a new migration instead.

### 5. Use Descriptive Messages

```bash
# Good
alembic revision --autogenerate -m "Add requires_approval field to Timeline model"

# Bad
alembic revision --autogenerate -m "Update"
```

---

## Production Workflow

### Development

1. Make model changes in `app.py`
2. Generate migration: `alembic revision --autogenerate -m "Description"`
3. Review migration file
4. Apply locally: `alembic upgrade head`
5. Test thoroughly
6. Commit migration to Git

### Staging/Production

1. Pull latest code (includes migration files)
2. Backup database: `cp instance/itimeline.db instance/itimeline.db.backup`
3. Apply migrations: `alembic upgrade head`
4. Verify application works
5. If issues, rollback: `alembic downgrade -1` and restore backup

---

## Common Commands Reference

```bash
# Setup
alembic init alembic                          # Initialize Alembic
alembic revision --autogenerate -m "msg"      # Auto-generate migration
alembic revision -m "msg"                     # Create empty migration

# Apply
alembic upgrade head                          # Apply all pending migrations
alembic upgrade +1                            # Apply next migration
alembic downgrade -1                          # Revert last migration
alembic downgrade base                        # Revert all migrations

# Info
alembic current                               # Show current migration
alembic history                               # Show all migrations
alembic history --verbose                     # Show detailed history
alembic show <revision>                       # Show specific migration

# Stamps (for existing databases)
alembic stamp head                            # Mark database as up-to-date
```

---

## Troubleshooting

### "Target database is not up to date"

```bash
alembic stamp head
```

This marks your current database state as the latest migration.

### "Can't locate revision identified by 'xxxx'"

Your migration files are out of sync. Check:
1. All migration files are in `alembic/versions/`
2. Git pull to get latest migrations
3. Check `alembic_version` table in database

### "Multiple head revisions are present"

You have conflicting migrations. Merge them:

```bash
alembic merge -m "Merge migrations" <rev1> <rev2>
```

---

## Migration Checklist for Production

Before deploying schema changes to production:

- [ ] Migration tested locally with real data
- [ ] Migration reviewed by team
- [ ] Database backup created
- [ ] Downgrade path tested
- [ ] Application code compatible with both old and new schema (for zero-downtime)
- [ ] Monitoring/alerts configured
- [ ] Rollback plan documented

---

## Zero-Downtime Migrations

For production systems that can't have downtime:

### Phase 1: Add Column (Nullable)
```python
# Migration 1: Add column as nullable
op.add_column('timeline', sa.Column('requires_approval', sa.Boolean(), nullable=True))
```

### Phase 2: Backfill Data
```python
# Migration 2: Set default values
op.execute("UPDATE timeline SET requires_approval = 0 WHERE requires_approval IS NULL")
```

### Phase 3: Make Non-Nullable
```python
# Migration 3: Add NOT NULL constraint
op.alter_column('timeline', 'requires_approval', nullable=False)
```

This allows the application to run during the migration process.

---

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Database Migration Best Practices](https://www.postgresql.org/docs/current/ddl-alter.html)

---

## Notes

- **Development**: Database resets are acceptable
- **Production**: ALWAYS use migrations, NEVER reset database
- **Backup**: Always backup before applying migrations in production
- **Test**: Test migrations on staging environment first
