"""
Standardize case for all timelines and tags.

This script:
1. Finds all timelines and capitalizes their names
2. Finds all tags and standardizes their case (lowercase for storage)
3. Ensures proper associations between timelines and tags

Run this script once to standardize case across the system.
"""

from app import app, db, Timeline, Event, Tag
from flask import Flask
import sys

def standardize_case():
    with app.app_context():
        print("Starting case standardization script...")
        
        # Standardize timeline names (capitalize)
        timelines = Timeline.query.all()
        print(f"Found {len(timelines)} timelines to process")
        
        for timeline in timelines:
            # Skip timelines with '#' prefix (these will be handled by the other script)
            if timeline.name.startswith('#'):
                continue
                
            old_name = timeline.name
            # Use ALL CAPS for timeline names
            new_name = timeline.name.upper()
            
            if old_name != new_name:
                print(f"Updating timeline: '{old_name}' -> '{new_name}'")
                timeline.name = new_name
        
        # Standardize tag names (lowercase for storage)
        tags = Tag.query.all()
        print(f"Found {len(tags)} tags to process")
        
        for tag in tags:
            old_name = tag.name
            # Lowercase the tag name for consistent storage
            new_name = tag.name.lower()
            
            if old_name != new_name:
                print(f"Updating tag: '{old_name}' -> '{new_name}'")
                tag.name = new_name
        
        # Commit all changes
        try:
            db.session.commit()
            print("All changes committed successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing changes: {str(e)}")
            return False
        
        return True

if __name__ == "__main__":
    success = standardize_case()
    sys.exit(0 if success else 1)
