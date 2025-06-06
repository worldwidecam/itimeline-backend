"""
Migration script to add community timeline features to the database.

This script adds:
1. A visibility field to the Timeline model (public/private)
2. A privacy_changed_at field to track when privacy was last changed
3. A TimelineMember table to track timeline memberships and roles

Usage:
    from migrations.add_community_timeline_features import run_migration
    run_migration()
"""

import os
import sys
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import inspect

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db

def run_migration():
    """
    Add community timeline features to the database.
    """
    print("Starting migration: Adding community timeline features")
    
    try:
        with app.app_context():
            # Get inspector to check existing schema
            inspector = inspect(db.engine)
            
            # 1. Check and add visibility field to Timeline model
            timeline_columns = [col['name'] for col in inspector.get_columns('timeline')]
            if 'visibility' not in timeline_columns:
                db.session.execute(sa.text('ALTER TABLE timeline ADD COLUMN visibility VARCHAR(20) NOT NULL DEFAULT "public"'))
                print("Added visibility field to Timeline model")
            else:
                print("Visibility field already exists in Timeline model")
            
            # 2. Check and add privacy_changed_at field to Timeline model
            if 'privacy_changed_at' not in timeline_columns:
                db.session.execute(sa.text('ALTER TABLE timeline ADD COLUMN privacy_changed_at DATETIME'))
                print("Added privacy_changed_at field to Timeline model")
            else:
                print("Privacy_changed_at field already exists in Timeline model")
            
            # 3. Create TimelineMember table if it doesn't exist
            if not inspector.has_table('timeline_member'):
                # Create the table using raw SQL to avoid model dependencies
                db.session.execute(sa.text('''
                    CREATE TABLE timeline_member (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timeline_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        role VARCHAR(20) NOT NULL DEFAULT 'member',
                        joined_at DATETIME NOT NULL,
                        invited_by INTEGER,
                        FOREIGN KEY (timeline_id) REFERENCES timeline (id),
                        FOREIGN KEY (user_id) REFERENCES user (id),
                        FOREIGN KEY (invited_by) REFERENCES user (id),
                        UNIQUE (timeline_id, user_id)
                    )
                '''))
                print("Created TimelineMember table")
            else:
                print("TimelineMember table already exists")
            
            # 4. Add initial admin entries for existing timelines
            # Get all existing timelines and their creators
            timelines = db.session.execute(
                sa.text('SELECT id, created_by FROM timeline WHERE created_by IS NOT NULL')
            ).fetchall()
            
            # For each timeline, check if admin entry exists and add if needed
            admin_count = 0
            for timeline_id, created_by in timelines:
                # Check if admin entry already exists
                existing = db.session.execute(
                    sa.text('SELECT id FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid'),
                    {'tid': timeline_id, 'uid': created_by}
                ).fetchone()
                
                if not existing:
                    db.session.execute(
                        sa.text('INSERT INTO timeline_member (timeline_id, user_id, role, joined_at) '
                        'VALUES (:timeline_id, :user_id, :role, :joined_at)'),
                        {
                            'timeline_id': timeline_id,
                            'user_id': created_by,
                            'role': 'admin',
                            'joined_at': datetime.now()
                        }
                    )
                    admin_count += 1
            
            db.session.commit()
            print(f"Added {admin_count} admin entries for existing timelines")
            print("Migration completed successfully")
            
    except Exception as e:
        db.session.rollback()
        print(f"Error during migration: {str(e)}")
        raise

if __name__ == '__main__':
    run_migration()
