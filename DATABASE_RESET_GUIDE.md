# Database Reset Guide (Development Only)

## ⚠️ WARNING: Development Only

**This guide is ONLY for local development. NEVER delete the database in production!**

For production, always use Alembic migrations (see `MIGRATION_GUIDE.md`).

---

## When to Reset Database

Reset your local database when:
- ✅ Testing new schema changes
- ✅ Schema conflicts after pulling new code
- ✅ Want to start fresh with clean test data
- ✅ Database corruption during development

**Do NOT reset when:**
- ❌ In production environment
- ❌ You want to keep existing test data
- ❌ You can use migrations instead (preferred)

---

## How to Delete Database File

### Option 1: File Explorer (Easiest)

1. Open File Explorer
2. Navigate to: `C:\Users\Arias\Documents\Github\itimeline-backend\instance\`
3. Find the file: `itimeline.db`
4. Right-click → **Delete** (or press Delete key)
5. Confirm deletion

### Option 2: PowerShell

```powershell
# Navigate to backend directory
cd C:\Users\Arias\Documents\Github\itimeline-backend

# Delete database
Remove-Item instance\itimeline.db

# Verify deletion
Test-Path instance\itimeline.db  # Should return False
```

### Option 3: VS Code

1. Open VS Code
2. In the file explorer panel (left side)
3. Navigate to: `itimeline-backend/instance/`
4. Right-click `itimeline.db`
5. Select **Delete**
6. Confirm deletion

### Option 4: Command Prompt

```cmd
cd C:\Users\Arias\Documents\Github\itimeline-backend
del instance\itimeline.db
```

---

## Complete Reset Process

### Step-by-Step

1. **Stop the Backend**
   - Go to terminal running backend
   - Press `Ctrl+C`
   - Wait for "Server stopped" message

2. **Delete Database File**
   - Use any method above
   - File location: `instance\itimeline.db`

3. **Restart Backend**
   ```bash
   python app.py
   ```
   - Database will automatically recreate
   - All tables will be created from models
   - Database will be empty (no users, timelines, events)

4. **Verify Success**
   - Check backend terminal for: "Database initialized"
   - Check frontend loads without errors
   - Try creating a test timeline

---

## What Happens During Reset

### Deleted
- ❌ All users
- ❌ All timelines
- ❌ All events
- ❌ All memberships
- ❌ All reports
- ❌ All action cards

### Preserved
- ✅ Model definitions (in `app.py`)
- ✅ Backend code
- ✅ Frontend code
- ✅ Uploaded media files (in `static/uploads/`)

### Recreated
- ✅ Empty database with correct schema
- ✅ All tables based on current models
- ✅ Ready for new test data

---

## After Reset: Creating Test Data

### 1. Create Test User

```bash
# In backend directory
python
```

```python
from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    user = User(
        username='testuser',
        email='test@example.com',
        password_hash=generate_password_hash('password123')
    )
    db.session.add(user)
    db.session.commit()
    print(f"Created user ID: {user.id}")
```

### 2. Login via Frontend

- Navigate to login page
- Username: `testuser`
- Password: `password123`

### 3. Create Test Timeline

- Use frontend to create a community timeline
- Add some test events
- Test membership features

---

## Troubleshooting

### "File not found" Error

**Problem**: `instance\itimeline.db` doesn't exist

**Solution**: Database already deleted or never created. Just restart backend.

### "Permission denied" Error

**Problem**: File is locked by another process

**Solution**:
1. Stop backend completely (Ctrl+C)
2. Close any database browser tools (DB Browser for SQLite, etc.)
3. Try deleting again

### Backend Won't Start After Reset

**Problem**: Error during database recreation

**Solution**:
1. Check for syntax errors in models (`app.py`)
2. Check backend terminal for specific error
3. Ensure all required packages installed: `pip install -r requirements.txt`

### Frontend Still Shows Old Data

**Problem**: Frontend caching old data

**Solution**:
1. Clear browser localStorage:
   - Open DevTools (F12)
   - Application tab → Local Storage
   - Right-click → Clear
2. Hard refresh: `Ctrl+Shift+R`

---

## Database File Details

### File Information

- **Filename**: `itimeline.db`
- **Location**: `itimeline-backend/instance/`
- **Type**: SQLite database
- **Size**: Varies (typically 100KB - 10MB for development)
- **Git Status**: Ignored (in `.gitignore`)

### Why It's Ignored in Git

The database file is in `.gitignore` because:
1. Contains user data (shouldn't be in version control)
2. Each developer has their own local database
3. Production has its own separate database
4. Database files are binary (not good for Git diffs)

### What IS in Git

- ✅ Schema definitions (`app.py` models)
- ✅ Migration files (`alembic/versions/`)
- ✅ Database configuration (`alembic.ini`)
- ❌ Actual database file (`instance/itimeline.db`)

---

## Alternative: Migrations (Preferred)

Instead of deleting the database, consider using migrations:

```bash
# After changing models
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

**Benefits**:
- ✅ Keeps existing data
- ✅ Safer for production
- ✅ Reversible changes
- ✅ Team can sync schema changes

See `MIGRATION_GUIDE.md` for full details.

---

## Quick Reference

```bash
# Delete database (PowerShell)
Remove-Item instance\itimeline.db

# Restart backend
python app.py

# Verify database recreated
Test-Path instance\itimeline.db  # Should return True
```

---

## Production Reminder

🚨 **NEVER delete the database in production!**

For production schema changes:
1. Create migration: `alembic revision --autogenerate -m "Description"`
2. Test locally: `alembic upgrade head`
3. Backup production: `pg_dump > backup.sql`
4. Apply to production: `alembic upgrade head`
5. Verify application works

See `MIGRATION_GUIDE.md` for production workflow.
