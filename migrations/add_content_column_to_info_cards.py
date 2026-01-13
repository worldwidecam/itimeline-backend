#!/usr/bin/env python
"""
Migration: Add content column to community_info_card table for mention/embed support
This uses ALTER TABLE to preserve existing data (backwards compatible)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from sqlalchemy import text as _sql_text

def run_migration():
    """Add content column to community_info_card table"""
    with app.app_context():
        try:
            print("[INFO] Starting migration: add content column to community_info_card")
            
            # Check if column already exists
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('community_info_card')]
            
            if 'content' in columns:
                print("[INFO] Column 'content' already exists, skipping migration")
                return True
            
            print("[INFO] Adding 'content' column to community_info_card table...")
            
            # Add content column (nullable for backwards compatibility)
            db.session.execute(_sql_text("""
                ALTER TABLE community_info_card
                ADD COLUMN content TEXT NULL
            """))
            
            db.session.commit()
            print("[SUCCESS] Migration completed successfully")
            print("[INFO] Existing cards will use plain text descriptions (backwards compatible)")
            print("[INFO] New cards can use JSON content with mentions and embeds")
            return True
            
        except Exception as e:
            print(f"[ERROR] Migration failed: {str(e)}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
