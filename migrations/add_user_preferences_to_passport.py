"""
Migration: Add preferences_json column to user_passport table for storing user preferences

- Column: preferences_json TEXT NOT NULL DEFAULT '{}'
- Database: PostgreSQL
- Safety: Uses IF NOT EXISTS to be idempotent
"""

from datetime import datetime
from sqlalchemy import text


def run_migration(db):
    """
    Execute the migration using the provided SQLAlchemy db from app.py
    """
    with db.engine.begin() as conn:
        # Add column if it doesn't exist
        conn.execute(text(
            """
            ALTER TABLE IF EXISTS user_passport
            ADD COLUMN IF NOT EXISTS preferences_json TEXT NOT NULL DEFAULT '{}';
            """
        ))

        # Ensure any NULLs (if column existed without default) are backfilled
        conn.execute(text(
            """
            UPDATE user_passport
            SET preferences_json = '{}'
            WHERE preferences_json IS NULL;
            """
        ))

        # Touch last_updated to now for rows so clients can re-pull
        conn.execute(text(
            """
            UPDATE user_passport
            SET last_updated = :now
            WHERE last_updated IS NULL;
            """
        ), {"now": datetime.now()})

        print("Migration add_user_preferences_to_passport applied successfully")


if __name__ == "__main__":
    # Allow running standalone: import app and run
    from app import db
    run_migration(db)
