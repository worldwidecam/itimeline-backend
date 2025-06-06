"""
Apply Community Timeline Schema Changes

This script applies all the necessary database schema changes for community timelines.
It runs the migration scripts in the correct order and updates the database.

Usage:
    python apply_community_schema.py
"""

import os
import sys
from datetime import datetime

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import app, db
from migrations.add_community_timeline_features import run_migration as add_community_features
from migrations.add_post_sharing import run_migration as add_post_sharing

def apply_schema_changes():
    """Apply all schema changes for community timelines"""
    print("Starting community timeline schema migration...")
    
    try:
        # Run migrations in order
        with app.app_context():
            # 1. Add community timeline features
            print("\n=== Adding Community Timeline Features ===")
            add_community_features()
            
            # 2. Add post sharing functionality
            print("\n=== Adding Post Sharing Functionality ===")
            add_post_sharing()
            
            print("\n=== Migration Complete ===")
            print("Community timeline schema has been successfully applied.")
            print("You can now use the community timeline features.")
            
    except Exception as e:
        print(f"\nError during migration: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    apply_schema_changes()
