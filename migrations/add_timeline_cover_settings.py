"""
Migration script to add timeline cover image settings columns.

Adds to timeline table:
1. cover_image_url (TEXT, nullable)
2. cover_upload_enabled (BOOLEAN, default TRUE, not null)

Usage:
    from migrations.add_timeline_cover_settings import run_migration
    run_migration()
"""

import os
import sys
import sqlalchemy as sa
from sqlalchemy import inspect

# Add parent directory for app import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db


def run_migration():
    print("Starting migration: add timeline cover settings")

    try:
        with app.app_context():
            inspector = inspect(db.engine)
            timeline_columns = [col['name'] for col in inspector.get_columns('timeline')]

            if 'cover_image_url' not in timeline_columns:
                db.session.execute(sa.text('ALTER TABLE timeline ADD COLUMN cover_image_url TEXT'))
                print("Added timeline.cover_image_url")
            else:
                print("timeline.cover_image_url already exists")

            if 'cover_upload_enabled' not in timeline_columns:
                db.session.execute(sa.text('ALTER TABLE timeline ADD COLUMN cover_upload_enabled BOOLEAN NOT NULL DEFAULT TRUE'))
                print("Added timeline.cover_upload_enabled")
            else:
                print("timeline.cover_upload_enabled already exists")

            db.session.commit()
            print("Migration completed successfully")
    except Exception as exc:
        db.session.rollback()
        print(f"Migration failed: {exc}")
        raise


if __name__ == '__main__':
    run_migration()
