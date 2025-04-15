import os
import sqlite3
from datetime import datetime, timedelta

def check_database():
    """Check the database for recent media uploads"""
    try:
        # Connect to the database
        db_path = os.path.join('instance', 'timeline.db')
        if not os.path.exists(db_path):
            print(f"Database file not found at: {db_path}")
            return
        
        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the events table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        if not cursor.fetchone():
            print("Events table not found in database")
            conn.close()
            return
        
        # Get column names from the events table
        cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"Columns in events table: {columns}")
        
        # Check for recent media uploads
        print("\nRecent events with media (last 24 hours):")
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d %H:%M:%S')
        
        # Adjust query based on available columns
        if 'media_url' in columns:
            media_col = 'media_url'
        elif 'url' in columns:
            media_col = 'url'
        else:
            print("No media URL column found in events table")
            conn.close()
            return
        
        # Check if created_at column exists
        date_col = 'created_at' if 'created_at' in columns else 'date'
        
        # Query for recent events with media
        query = f"SELECT id, title, {media_col}, {date_col} FROM events WHERE {media_col} IS NOT NULL ORDER BY {date_col} DESC LIMIT 10"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("No recent media events found")
        else:
            for row in rows:
                print(f"ID: {row[0]}, Title: {row[1]}, Media URL: {row[2]}, Date: {row[3]}")
        
        # Specifically look for "media test 7"
        print("\nLooking for 'media test 7':")
        cursor.execute(f"SELECT id, title, {media_col}, {date_col} FROM events WHERE title LIKE ? ORDER BY {date_col} DESC", ('%media test 7%',))
        media_test_rows = cursor.fetchall()
        
        if not media_test_rows:
            print("No 'media test 7' events found")
        else:
            for row in media_test_rows:
                print(f"ID: {row[0]}, Title: {row[1]}, Media URL: {row[2]}, Date: {row[3]}")
        
        conn.close()
    except Exception as e:
        print(f"Error checking database: {str(e)}")

def check_uploads_directory():
    """Check the uploads directory for recent files"""
    try:
        uploads_dir = os.path.join('static', 'uploads')
        if not os.path.exists(uploads_dir):
            print(f"Uploads directory not found at: {uploads_dir}")
            return
        
        print(f"\nChecking uploads directory: {uploads_dir}")
        files = os.listdir(uploads_dir)
        
        if not files:
            print("No files found in uploads directory")
            return
        
        # Get file info with creation/modification time
        file_info = []
        for filename in files:
            file_path = os.path.join(uploads_dir, filename)
            if os.path.isfile(file_path):
                mtime = os.path.getmtime(file_path)
                size = os.path.getsize(file_path)
                file_info.append((filename, mtime, size))
        
        # Sort by modification time (newest first)
        file_info.sort(key=lambda x: x[1], reverse=True)
        
        # Print recent files (last 10)
        print("\nMost recent files in uploads directory:")
        for i, (filename, mtime, size) in enumerate(file_info[:10]):
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            size_kb = size / 1024
            print(f"{i+1}. {filename} - {mtime_str} - {size_kb:.2f} KB")
    except Exception as e:
        print(f"Error checking uploads directory: {str(e)}")

if __name__ == "__main__":
    print("=== Checking for recent media uploads ===")
    check_database()
    check_uploads_directory()
    print("\n=== Check complete ===")
