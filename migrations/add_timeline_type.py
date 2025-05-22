"""
QUARANTINED: This script is no longer needed and is up for deletion.
The database schema has been updated using init_db.py and the timeline_type field
is now part of the Timeline model. This file is kept only for documentation purposes.

Migration script to add timeline_type field to existing timelines.
This script updates all existing timelines to have a 'hashtag' timeline_type.

Usage:
    python migrations/add_timeline_type.py
"""

import os
import sys
from datetime import datetime

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, Timeline

def run_migration():
    """
    Add timeline_type field to all existing timelines.
    Sets the default value to 'hashtag' for all existing records.
    """
    print("Starting migration: Adding timeline_type field to existing timelines")
    
    try:
        # Get all existing timelines
        timelines = Timeline.query.all()
        count = 0
        
        # Update each timeline to have the 'hashtag' type
        for timeline in timelines:
            timeline.timeline_type = 'hashtag'
            count += 1
        
        # Commit the changes
        db.session.commit()
        
        print(f"Migration completed successfully: Updated {count} timelines")
        print(f"All existing timelines now have the 'hashtag' timeline_type")
        
    except Exception as e:
        db.session.rollback()
        print(f"Error during migration: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    # Run the migration within the application context
    with app.app_context():
        run_migration()
