"""
Migration script to add post sharing functionality to the database.

This script adds:
1. EventTimelineAssociation table to track post sharing between communities

Usage:
    from migrations.add_post_sharing import run_migration
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
    Add post sharing functionality to the database.
    """
    print("Starting migration: Adding post sharing functionality")
    
    try:
        with app.app_context():
            # Get inspector to check existing schema
            inspector = inspect(db.engine)
            
            # 1. Create EventTimelineAssociation table if it doesn't exist
            if not inspector.has_table('event_timeline_association'):
                # Create the table using raw SQL to avoid model dependencies
                db.session.execute(sa.text('''
                    CREATE TABLE event_timeline_association (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        timeline_id INTEGER NOT NULL,
                        shared_by INTEGER NOT NULL,
                        shared_at DATETIME NOT NULL,
                        source_timeline_id INTEGER,
                        FOREIGN KEY (event_id) REFERENCES event (id),
                        FOREIGN KEY (timeline_id) REFERENCES timeline (id),
                        FOREIGN KEY (shared_by) REFERENCES user (id),
                        FOREIGN KEY (source_timeline_id) REFERENCES timeline (id),
                        UNIQUE (event_id, timeline_id)
                    )
                '''))
                print("Created EventTimelineAssociation table")
            else:
                print("EventTimelineAssociation table already exists")
            
            # 2. Check if we need to backfill existing events with associations
            # First check if any associations exist
            count = db.session.execute(
                sa.text('SELECT COUNT(*) FROM event_timeline_association')
            ).scalar()
            
            if count == 0:
                # Get all existing events and their timelines
                events = db.session.execute(
                    sa.text('SELECT e.id, e.timeline_id, e.created_by, e.created_at '
                    'FROM event e WHERE e.timeline_id IS NOT NULL')
                ).fetchall()
                
                # For each event, add an association entry
                for event_id, timeline_id, created_by, created_at in events:
                    if created_by is None:
                        # Skip events without a creator
                        continue
                    
                    db.session.execute(
                        sa.text('INSERT INTO event_timeline_association '
                        '(event_id, timeline_id, shared_by, shared_at, source_timeline_id) '
                        'VALUES (:event_id, :timeline_id, :shared_by, :shared_at, :source_timeline_id)'),
                        {
                            'event_id': event_id,
                            'timeline_id': timeline_id,
                            'shared_by': created_by,
                            'shared_at': created_at or datetime.now(),
                            'source_timeline_id': timeline_id  # Same as timeline_id for original posts
                        }
                    )
                
                db.session.commit()
                print(f"Added {len(events)} association entries for existing events")
            else:
                print("Association entries already exist, skipping backfill")
            
            print("Migration completed successfully")
            
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    run_migration()
