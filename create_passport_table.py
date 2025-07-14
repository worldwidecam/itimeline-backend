import sqlite3
import json
from datetime import datetime

def create_passport_table():
    """Create the user_passport table in the instance/timeline_forum.db database and populate it with membership data."""
    try:
        print("Creating user_passport table in instance/timeline_forum.db...")
        # Connect to the database
        conn = sqlite3.connect('instance/timeline_forum.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if user_passport table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
        if cursor.fetchone():
            print("user_passport table already exists. Dropping it to recreate...")
            cursor.execute("DROP TABLE user_passport")
            conn.commit()
        
        # Create the user_passport table
        cursor.execute("""
            CREATE TABLE user_passport (
                user_id INTEGER PRIMARY KEY,
                memberships_json TEXT,
                last_updated TIMESTAMP
            )
        """)
        conn.commit()
        print("user_passport table created successfully.")
        
        # Get all users
        cursor.execute("SELECT id FROM user")
        users = cursor.fetchall()
        
        # For each user, get their memberships and create a passport record
        for user in users:
            user_id = user['id']
            print(f"Processing user ID: {user_id}")
            
            # Get all memberships for this user
            cursor.execute("""
                SELECT tm.timeline_id, tm.role, tm.is_active_member, t.name as timeline_name, t.visibility, t.timeline_type
                FROM timeline_member tm
                JOIN timeline t ON tm.timeline_id = t.id
                WHERE tm.user_id = ? AND tm.is_active_member = 1
            """, (user_id,))
            memberships = cursor.fetchall()
            
            # Also get timelines created by this user (they should be members even if no explicit membership)
            cursor.execute("""
                SELECT id as timeline_id, 'admin' as role, 1 as is_active_member, name as timeline_name, visibility, timeline_type
                FROM timeline
                WHERE created_by = ? AND id NOT IN (
                    SELECT timeline_id FROM timeline_member WHERE user_id = ?
                )
            """, (user_id, user_id))
            created_timelines = cursor.fetchall()
            
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
            cursor.execute("""
                INSERT INTO user_passport (user_id, memberships_json, last_updated)
                VALUES (?, ?, ?)
            """, (user_id, memberships_json, datetime.now().isoformat()))
            
            print(f"  - Added {len(formatted_memberships)} memberships to passport for user {user_id}")
        
        conn.commit()
        print("All user passports created successfully.")
        
        # Verify the user_passport table
        cursor.execute("SELECT COUNT(*) as count FROM user_passport")
        count = cursor.fetchone()['count']
        print(f"user_passport table now has {count} records.")
        
    except Exception as e:
        print(f"Error creating user_passport table: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    create_passport_table()
