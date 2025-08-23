#!/usr/bin/env python3
"""
check_postgres_counts.py

Read-only verification script to print row counts for key PostgreSQL tables.
SAFE TO DELETE after use.

This does NOT modify any data.
"""
import os
import sys
from contextlib import closing

try:
    import psycopg2
except ImportError as e:
    print("[ERROR] psycopg2 is not installed. Please install requirements for the backend.")
    sys.exit(1)

# Resolve DATABASE_URL with fallback to local dev connection
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:death2therich@localhost:5432/itimeline_test"

TABLES = [
    "user",
    "user_music",
    "timeline",
    "timeline_member",
    "timeline_action",
    "tag",
    "event",
    "event_tags",
    "event_timeline_refs",
    "event_timeline_association",
    "post",
    "comment",
    "token_blocklist",
    # Passport table is important for verification
    "user_passport",
]


def mask_url(url: str) -> str:
    try:
        # postgresql://user:pass@host:port/db
        if "@" in url and "://" in url:
            scheme, rest = url.split("://", 1)
            creds, host = rest.split("@", 1)
            if ":" in creds:
                user, _ = creds.split(":", 1)
                return f"{scheme}://{user}:***@{host}"
    except Exception:
        pass
    return url


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,)
    )
    return cursor.fetchone()[0]


def main():
    print("PostgreSQL row count verification (read-only) — SAFE TO DELETE")
    print("Using DATABASE_URL:", mask_url(DATABASE_URL))

    try:
        with closing(psycopg2.connect(DATABASE_URL)) as conn:
            with closing(conn.cursor()) as cur:
                totals = 0
                missing = []
                print("\n[Tables]")
                for name in TABLES:
                    if not table_exists(cur, name):
                        print(f" - {name}: [MISSING]")
                        missing.append(name)
                        continue
                    cur.execute(f'SELECT COUNT(*) FROM "{name}"')
                    count = cur.fetchone()[0]
                    totals += count
                    print(f" - {name}: {count}")
                print("\n[Summary]")
                print(f" Total rows across listed tables: {totals}")
                if missing:
                    print(" Missing tables:", ", ".join(missing))
                print("\nDone.")
    except Exception as e:
        print("[ERROR] Could not connect/query Postgres:", str(e))
        sys.exit(2)


if __name__ == "__main__":
    main()
