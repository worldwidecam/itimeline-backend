import sqlite3
import json
from datetime import datetime

def update_passport_db_path():
    """
    Update the user passport table to use the correct database path.
    This script:
    1. Copies user passport data from timeline_forum.db to instance/timeline_forum.db (if it exists)
    2. Updates the app.py and routes/passport.py files to use the correct database path
    """
    try:
        print("Checking if user_passport table exists in root database...")
        # Check if user_passport table exists in root database
        try:
            conn_root = sqlite3.connect('timeline_forum.db')
            conn_root.row_factory = sqlite3.Row
            cursor_root = conn_root.cursor()
            
            cursor_root.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
            has_root_table = cursor_root.fetchone() is not None
            
            if has_root_table:
                print("Found user_passport table in root database.")
                # Get all records from root database
                cursor_root.execute("SELECT * FROM user_passport")
                root_passports = cursor_root.fetchall()
                print(f"Found {len(root_passports)} passport records in root database.")
            else:
                print("No user_passport table found in root database.")
                root_passports = []
        except Exception as e:
            print(f"Error accessing root database: {str(e)}")
            root_passports = []
            has_root_table = False
        finally:
            if 'conn_root' in locals():
                conn_root.close()
        
        # Now check the instance database
        print("\nChecking instance database...")
        conn_instance = sqlite3.connect('instance/timeline_forum.db')
        conn_instance.row_factory = sqlite3.Row
        cursor_instance = conn_instance.cursor()
        
        # Check if user_passport table exists in instance database
        cursor_instance.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
        has_instance_table = cursor_instance.fetchone() is not None
        
        if not has_instance_table:
            print("Creating user_passport table in instance database...")
            cursor_instance.execute("""
                CREATE TABLE user_passport (
                    user_id INTEGER PRIMARY KEY,
                    memberships_json TEXT,
                    last_updated TIMESTAMP
                )
            """)
            conn_instance.commit()
        else:
            print("user_passport table already exists in instance database.")
        
        # Copy records from root to instance if needed
        if has_root_table and len(root_passports) > 0:
            print("\nCopying passport records from root to instance database...")
            for passport in root_passports:
                user_id = passport['user_id']
                memberships_json = passport['memberships_json']
                last_updated = passport['last_updated']
                
                # Check if user already has a passport in instance database
                cursor_instance.execute("SELECT user_id FROM user_passport WHERE user_id = ?", (user_id,))
                if cursor_instance.fetchone() is None:
                    cursor_instance.execute(
                        "INSERT INTO user_passport (user_id, memberships_json, last_updated) VALUES (?, ?, ?)",
                        (user_id, memberships_json, last_updated)
                    )
                    print(f"  - Copied passport for user ID {user_id}")
                else:
                    print(f"  - User ID {user_id} already has a passport in instance database, skipping")
            
            conn_instance.commit()
        
        # Now populate the user_passport table with actual membership data
        print("\nPopulating user_passport table with actual membership data...")
        # Get all users
        cursor_instance.execute("SELECT id FROM user")
        users = cursor_instance.fetchall()
        
        for user in users:
            user_id = user['id']
            print(f"Processing user ID: {user_id}")
            
            # Get all memberships for this user
            cursor_instance.execute("""
                SELECT tm.timeline_id, tm.role, tm.is_active_member, t.name as timeline_name, t.visibility, t.timeline_type
                FROM timeline_member tm
                JOIN timeline t ON tm.timeline_id = t.id
                WHERE tm.user_id = ? AND tm.is_active_member = 1
            """, (user_id,))
            memberships = cursor_instance.fetchall()
            
            # Also get timelines created by this user (they should be members even if no explicit membership)
            cursor_instance.execute("""
                SELECT id as timeline_id, 'admin' as role, 1 as is_active_member, name as timeline_name, visibility, timeline_type
                FROM timeline
                WHERE created_by = ? AND id NOT IN (
                    SELECT timeline_id FROM timeline_member WHERE user_id = ?
                )
            """, (user_id, user_id))
            created_timelines = cursor_instance.fetchall()
            
            # Combine both sets
            all_memberships = list(memberships) + list(created_timelines)
            
            # Format memberships for JSON storage
            formatted_memberships = []
            for membership in all_memberships:
                # Only include community timelines
                if membership['timeline_type'] == 'community':
                    formatted_memberships.append({
                        'timeline_id': membership['timeline_id'],
                        'timeline_name': membership['timeline_name'],
                        'role': membership['role'],
                        'isMember': True,
                        'is_active_member': bool(membership['is_active_member']),
                        'timeline_visibility': membership['visibility']
                    })
            
            # Insert or update the user passport
            memberships_json = json.dumps(formatted_memberships)
            cursor_instance.execute("""
                INSERT OR REPLACE INTO user_passport (user_id, memberships_json, last_updated)
                VALUES (?, ?, ?)
            """, (user_id, memberships_json, datetime.now().isoformat()))
            
            print(f"  - Added {len(formatted_memberships)} memberships to passport for user {user_id}")
        
        conn_instance.commit()
        print("\nAll user passports updated successfully.")
        
        # Verify the user_passport table
        cursor_instance.execute("SELECT COUNT(*) as count FROM user_passport")
        count = cursor_instance.fetchone()['count']
        print(f"user_passport table now has {count} records.")
        
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the join button functionality")
        print("3. Verify that membership status persists after logout and login")
        
    except Exception as e:
        print(f"Error updating passport database path: {str(e)}")
    finally:
        if 'conn_instance' in locals():
            conn_instance.close()

if __name__ == "__main__":
    update_passport_db_path()
