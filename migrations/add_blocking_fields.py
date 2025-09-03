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
    # Use explicit transaction so DDL commits reliably
    try:
        dialect = engine.dialect.name
        print(f"Database dialect: {dialect}")
        table_name = 'timeline_member'
        pg_table = 'public.timeline_member'

        with engine.begin() as conn:
            print("[migration] Connected and transaction started")
            # Apply conservative timeouts so the script fails fast instead of hanging on locks
            if dialect == 'postgresql':
                conn.execute(text("SET application_name = 'itimeline_migration_add_blocking_fields'"))
                conn.execute(text("SET lock_timeout = '5s'"))            # wait max 5s for table lock
                conn.execute(text("SET statement_timeout = '15s'"))      # any single statement max 15s

            # Add is_blocked
            if not column_exists(engine, table_name, 'is_blocked'):
                try:
                    if dialect == 'postgresql':
                        conn.execute(text(f"ALTER TABLE {pg_table} ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"))
                    else:
                        conn.execute(text("ALTER TABLE timeline_member ADD COLUMN is_blocked BOOLEAN DEFAULT 0"))
                    print("Added column: is_blocked")
                except Exception as e:
                    print(f"Failed to add is_blocked: {e}")
                    if dialect == 'postgresql':
                        _log_pg_blockers(conn, pg_table)
                    raise
            else:
                print("Column already exists: is_blocked")

            # Add blocked_at
            if not column_exists(engine, table_name, 'blocked_at'):
                try:
                    if dialect == 'postgresql':
                        conn.execute(text(f"ALTER TABLE {pg_table} ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP NULL"))
                    else:
                        conn.execute(text("ALTER TABLE timeline_member ADD COLUMN blocked_at DATETIME NULL"))
                    print("Added column: blocked_at")
                except Exception as e:
                    print(f"Failed to add blocked_at: {e}")
                    if dialect == 'postgresql':
                        _log_pg_blockers(conn, pg_table)
                    raise
            else:
                print("Column already exists: blocked_at")

            # Add blocked_reason
            if not column_exists(engine, table_name, 'blocked_reason'):
                try:
                    if dialect == 'postgresql':
                        conn.execute(text(f"ALTER TABLE {pg_table} ADD COLUMN IF NOT EXISTS blocked_reason TEXT NULL"))
                    else:
                        conn.execute(text("ALTER TABLE timeline_member ADD COLUMN blocked_reason TEXT NULL"))
                    print("Added column: blocked_reason")
                except Exception as e:
                    print(f"Failed to add blocked_reason: {e}")
                    if dialect == 'postgresql':
                        _log_pg_blockers(conn, pg_table)
                    raise
            else:
                print("Column already exists: blocked_reason")

        print("Migration completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
        raise


def _log_pg_blockers(conn, qualified_table_name: str):
    """Log information about sessions that might be blocking DDL on the table.
    Postgres only.
    """
    try:
        # relname from qualified name
        rel = qualified_table_name.split('.')[-1]
        print("[diagnostics] Checking for blockers on table:", qualified_table_name)
        res = conn.execute(text(
            """
            SELECT a.pid, a.usename, a.state, a.wait_event_type, a.wait_event,
                   now() - a.query_start AS running_for, left(a.query, 200) AS query
            FROM pg_stat_activity a
            WHERE a.datname = current_database()
            ORDER BY a.query_start
            """
        )).mappings().all()
        for row in res:
            print(f" - pid={row['pid']}, user={row['usename']}, state={row['state']}, wait={row['wait_event_type']}/{row['wait_event']}, running_for={row['running_for']}, query=\n   {row['query']}")
        # Try NOWAIT lock as a definitive blocker check
        try:
            conn.execute(text(f"LOCK TABLE {qualified_table_name} IN ACCESS EXCLUSIVE MODE NOWAIT"))
            print("[diagnostics] NOWAIT lock acquired (no blockers at this instant)")
        except Exception as e:
            print(f"[diagnostics] Could not acquire NOWAIT lock on {qualified_table_name}: {e}")
            print("You can terminate a blocker with: SELECT pg_terminate_backend(<PID>);")
    except Exception as diag_e:
        print(f"[diagnostics] Failed to collect blocker info: {diag_e}")

if __name__ == '__main__':
    run_migration()
