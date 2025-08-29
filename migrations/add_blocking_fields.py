"""
Migration: add blocking fields to timeline_member

Adds columns:
- is_blocked BOOLEAN DEFAULT FALSE
- blocked_at TIMESTAMP NULL
- blocked_reason TEXT NULL

Safe to run multiple times.
Usage:
    # Optionally set DATABASE_URL, otherwise defaults to local SQLite file
    set DATABASE_URL=sqlite:///timeline_forum.db   # Windows PowerShell: $env:DATABASE_URL = 'sqlite:///timeline_forum.db'
    python migrations/add_blocking_fields.py
"""
import sys
import os
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# Create engine directly without importing Flask app (avoids app init side-effects)
def get_engine() -> Engine:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Default to local SQLite DB file at repo root
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        db_file = os.path.join(repo_root, 'timeline_forum.db')
        db_url = f"sqlite:///{db_file}"
        print(f"[migration] DATABASE_URL not set. Using local SQLite: {db_url}")
    else:
        print(f"[migration] Using DATABASE_URL: {db_url}")
    return sa.create_engine(db_url, future=True)

def column_exists(engine, table_name, column_name):
    insp = inspect(engine)
    for col in insp.get_columns(table_name):
        if col.get('name') == column_name:
            return True
    return False

def run_migration():
    print("Starting migration: add blocking fields to timeline_member")
    engine = get_engine()
    conn = engine.connect()
    try:
        # Determine dialect
        dialect = engine.dialect.name
        print(f"Database dialect: {dialect}")

        # Add is_blocked
        if not column_exists(engine, 'timeline_member', 'is_blocked'):
            if dialect == 'postgresql':
                conn.execute(text("ALTER TABLE timeline_member ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"))
            else:
                conn.execute(text("ALTER TABLE timeline_member ADD COLUMN is_blocked BOOLEAN DEFAULT 0"))
            print("Added column: is_blocked")
        else:
            print("Column already exists: is_blocked")

        # Add blocked_at
        if not column_exists(engine, 'timeline_member', 'blocked_at'):
            if dialect == 'postgresql':
                conn.execute(text("ALTER TABLE timeline_member ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP NULL"))
            else:
                conn.execute(text("ALTER TABLE timeline_member ADD COLUMN blocked_at DATETIME NULL"))
            print("Added column: blocked_at")
        else:
            print("Column already exists: blocked_at")

        # Add blocked_reason
        if not column_exists(engine, 'timeline_member', 'blocked_reason'):
            if dialect == 'postgresql':
                conn.execute(text("ALTER TABLE timeline_member ADD COLUMN IF NOT EXISTS blocked_reason TEXT NULL"))
            else:
                conn.execute(text("ALTER TABLE timeline_member ADD COLUMN blocked_reason TEXT NULL"))
            print("Added column: blocked_reason")
        else:
            print("Column already exists: blocked_reason")

        conn.close()
        print("Migration completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        try:
            conn.close()
        except Exception:
            pass
        raise

if __name__ == '__main__':
    run_migration()
