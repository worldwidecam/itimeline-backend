# Quick Migration Reference Card

## 🚀 First Time Setup (Run Once)

```bash
python setup_alembic.py
```

Then edit `alembic/env.py` (lines 7 and 21):
```python
from app import db
target_metadata = db.metadata
```

---

## 📝 Daily Workflow

### When You Change a Model

```bash
# 1. Make changes to app.py models
# 2. Generate migration
alembic revision --autogenerate -m "Add requires_approval field"

# 3. Review the generated file in alembic/versions/

# 4. Apply migration
alembic upgrade head

# 5. Test your app

# 6. Commit to Git
git add alembic/versions/*.py
git commit -m "Add migration: requires_approval field"
```

---

## 🔧 Common Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# See current migration
alembic current

# See migration history
alembic history
```

---

## ⚠️ Production Rules

1. **ALWAYS backup database before migration**
   ```bash
   cp instance/itimeline.db instance/itimeline.db.backup
   ```

2. **NEVER delete migration files** once they're applied

3. **ALWAYS test migrations locally first**

4. **ALWAYS commit migrations to Git**

---

## 🆘 Emergency Rollback

```bash
# Rollback last migration
alembic downgrade -1

# Restore database backup
cp instance/itimeline.db.backup instance/itimeline.db

# Restart application
```

---

## 📊 Migration File Structure

```
alembic/
├── versions/
│   ├── 001_initial_migration.py      # First migration
│   ├── 002_add_requires_approval.py  # Second migration
│   └── ...
├── env.py                             # Alembic configuration
└── script.py.mako                     # Migration template
```

**Important**: All files in `versions/` should be committed to Git!

---

## 🎯 Quick Troubleshooting

**Problem**: "Target database is not up to date"
```bash
alembic stamp head
```

**Problem**: Database out of sync
```bash
# Mark current state
alembic stamp head

# Or start fresh (development only!)
rm instance/itimeline.db
alembic upgrade head
```

**Problem**: Want to start over (development only!)
```bash
rm -rf alembic/versions/*
rm instance/itimeline.db
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

---

## 📚 Full Documentation

See `MIGRATION_GUIDE.md` for complete documentation.
