import os
import shutil
import sqlite3

def copy_db_to_root():
    """
    Copy the database from instance/timeline_forum.db to timeline_forum.db in the root directory.
    This ensures that the Flask app can access the database with the correct user data.
    """
    try:
        source_db = 'instance/timeline_forum.db'
        target_db = 'timeline_forum.db'
        
        print(f"Checking if source database exists: {source_db}")
        if not os.path.exists(source_db):
            print(f"Error: Source database {source_db} does not exist!")
            return
        
        print(f"Backing up existing target database if it exists: {target_db}")
        if os.path.exists(target_db):
            backup_db = f"{target_db}.bak"
            shutil.copy2(target_db, backup_db)
            print(f"Backup created as {backup_db}")
        
        print(f"Copying database from {source_db} to {target_db}")
        shutil.copy2(source_db, target_db)
        print("Database copied successfully")
        
        # Verify the copy by checking tables in both databases
        print("\nVerifying database copy...")
        
        # Check source database
        conn_source = sqlite3.connect(source_db)
        cursor_source = conn_source.cursor()
        cursor_source.execute("SELECT name FROM sqlite_master WHERE type='table'")
        source_tables = [row[0] for row in cursor_source.fetchall()]
        conn_source.close()
        
        # Check target database
        conn_target = sqlite3.connect(target_db)
        cursor_target = conn_target.cursor()
        cursor_target.execute("SELECT name FROM sqlite_master WHERE type='table'")
        target_tables = [row[0] for row in cursor_target.fetchall()]
        conn_target.close()
        
        print(f"Source database tables: {', '.join(source_tables)}")
        print(f"Target database tables: {', '.join(target_tables)}")
        
        # Check if user_passport table exists in target database
        if 'user_passport' in target_tables:
            print("user_passport table exists in the target database")
            
            # Check user_passport records
            conn = sqlite3.connect(target_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM user_passport")
            count = cursor.fetchone()['count']
            print(f"user_passport table has {count} records")
            conn.close()
        else:
            print("Warning: user_passport table does not exist in the target database")
        
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the join button functionality")
        print("3. Verify that membership status persists after logout and login")
        
    except Exception as e:
        print(f"Error copying database: {str(e)}")

if __name__ == "__main__":
    copy_db_to_root()
