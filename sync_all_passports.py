import sqlite3
import json
from datetime import datetime

def sync_all_user_passports():
    """
    Force sync all user passports with their membership data.
    This is a one-time fix to ensure all user passports have the correct membership data.
    """
    try:
        # Connect to database
        conn = sqlite3.connect('timeline_forum.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all users
        cursor.execute('SELECT id FROM user')
        users = cursor.fetchall()
        
        print(f"Found {len(users)} users to sync passports for")
        
        for user in users:
            user_id = user['id']
            print(f"Syncing passport for user {user_id}...")
            
            # Get all timeline memberships for the user
            cursor.execute('''
                SELECT tm.timeline_id, tm.role, tm.is_active_member, tm.joined_at,
                       t.name as timeline_name, t.visibility, t.timeline_type
                FROM timeline_member tm
                JOIN timeline t ON tm.timeline_id = t.id
                WHERE tm.user_id = ? AND tm.is_active_member = 1
            ''', (user_id,))
            
            memberships = []
            for row in cursor.fetchall():
                memberships.append({
                    'timeline_id': row['timeline_id'],
                    'role': row['role'],
                    'is_active_member': bool(row['is_active_member']),
                    'isMember': bool(row['is_active_member']),  # Add explicit isMember field for frontend compatibility
                    'joined_at': row['joined_at'],
                    'timeline_name': row['timeline_name'],
                    'visibility': row['visibility'],
                    'timeline_type': row['timeline_type']
                })
            
            # Also add timelines created by the user (they're implicitly admins)
            cursor.execute('''
                SELECT id as timeline_id, name as timeline_name, visibility, timeline_type, created_at
                FROM timeline
                WHERE created_by = ? AND id NOT IN (
                    SELECT timeline_id FROM timeline_member WHERE user_id = ?
                )
            ''', (user_id, user_id))
            
            for row in cursor.fetchall():
                memberships.append({
                    'timeline_id': row['timeline_id'],
                    'role': 'admin',  # Creator is always admin
                    'is_active_member': True,
                    'isMember': True,
                    'joined_at': row['created_at'],
                    'timeline_name': row['timeline_name'],
                    'visibility': row['visibility'],
                    'timeline_type': row['timeline_type'],
                    'is_creator': True
                })
            
            # For SiteOwner (user ID 1), add access to all timelines
            if int(user_id) == 1:
                cursor.execute('''
                    SELECT id as timeline_id, name as timeline_name, visibility, timeline_type, created_at
                    FROM timeline
                    WHERE id NOT IN (
                        SELECT timeline_id FROM timeline_member WHERE user_id = 1
                    )
                ''')
                
                for row in cursor.fetchall():
                    memberships.append({
                        'timeline_id': row['timeline_id'],
                        'role': 'SiteOwner',
                        'is_active_member': True,
                        'isMember': True,
                        'joined_at': row['created_at'],
                        'timeline_name': row['timeline_name'],
                        'visibility': row['visibility'],
                        'timeline_type': row['timeline_type'],
                        'is_site_owner': True
                    })
            
            # Update the user's passport with the latest membership data
            cursor.execute(
                'UPDATE user_passport SET memberships_json = ?, last_updated = ? WHERE user_id = ?',
                (json.dumps(memberships), datetime.now().isoformat(), user_id)
            )
            
            # If no passport exists, create one
            if cursor.rowcount == 0:
                cursor.execute(
                    'INSERT INTO user_passport (user_id, memberships_json, last_updated) VALUES (?, ?, ?)',
                    (user_id, json.dumps(memberships), datetime.now().isoformat())
                )
            
            print(f"  - Updated passport for user {user_id} with {len(memberships)} memberships")
        
        conn.commit()
        print("All user passports synced successfully!")
        
    except Exception as e:
        print(f"Error syncing user passports: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    sync_all_user_passports()
