import sys
import os
import sqlite3
from datetime import datetime

# Add the parent directory to the path so we can import from app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get the database path from environment or use default
from app import app, db

def run_migration():
    """
    Add music_public_id column to UserMusic table
    """
    try:
        print("Starting migration: Adding music_public_id column to UserMusic table")
        
        # Use SQLAlchemy engine to get connection
        connection = db.engine.connect()
        
        # Check if column already exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('user_music')]
        
        if 'music_public_id' not in columns:
            # Add the column
            connection.execute(db.text("ALTER TABLE user_music ADD COLUMN music_public_id VARCHAR(255)"))
            print("Successfully added music_public_id column to UserMusic table")
        else:
            print("Column music_public_id already exists in UserMusic table")
            
        connection.close()
        return True
        
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        return False

if __name__ == "__main__":
    with app.app_context():
        success = run_migration()
        if success:
            print("Migration completed successfully")
        else:
            print("Migration failed")
