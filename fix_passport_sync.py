"""
Fix the passport sync issue by updating all user passports with their complete membership data.
"""
import sqlite3
import json
from datetime import datetime

def fix_passport_sync():
    """
    Update all user passports with their complete membership data from the timeline_member table.
    This ensures that all memberships are properly reflected in the user passport.
    """
    print("Fixing User Passport Sync")
    print("========================\n")
    
    try:
        # Connect to the database
        conn = sqlite3.connect('instance/timeline_forum.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all users with active memberships
        cursor.execute("""
            SELECT DISTINCT user_id 
            FROM timeline_member 
            WHERE is_active_member = 1
        """)
        
        users = [row['user_id'] for row in cursor.fetchall()]
        print(f"Found {len(users)} users with active memberships")
        
        for user_id in users:
            print(f"\nProcessing user {user_id}...")
            
            # Get all timeline memberships for the user
            cursor.execute("""
                SELECT tm.timeline_id, tm.role, tm.is_active_member, tm.joined_at,
                       t.name as timeline_name, t.visibility, t.timeline_type
                FROM timeline_member tm
                JOIN timeline t ON tm.timeline_id = t.id
                WHERE tm.user_id = ? AND tm.is_active_member = 1
            """, (user_id,))
            
            memberships = []
            for row in cursor.fetchall():
                memberships.append({
                    'timeline_id': row['timeline_id'],
                    'timeline_name': row['timeline_name'],
                    'role': row['role'],
                    'is_active_member': bool(row['is_active_member']),
                    'isMember': bool(row['is_active_member']),  # Explicit isMember field for frontend compatibility
                    'joined_at': row['joined_at'],
                    'timeline_visibility': row['visibility'],
                    'timeline_type': row['timeline_type']
                })
            
            print(f"Found {len(memberships)} memberships for user {user_id}")
            
            # Also add timelines created by the user (they're implicitly admins)
            cursor.execute("""
                SELECT id as timeline_id, name as timeline_name, visibility, timeline_type, created_at
                FROM timeline
                WHERE created_by = ? AND id NOT IN (
                    SELECT timeline_id FROM timeline_member WHERE user_id = ?
                )
            """, (user_id, user_id))
            
            creator_count = 0
            for row in cursor.fetchall():
                memberships.append({
                    'timeline_id': row['timeline_id'],
                    'timeline_name': row['timeline_name'],
                    'role': 'admin',  # Creator is always admin
                    'is_active_member': True,
                    'isMember': True,
                    'joined_at': row['created_at'],
                    'timeline_visibility': row['visibility'],
                    'timeline_type': row['timeline_type'],
                    'is_creator': True
                })
                creator_count += 1
            
            if creator_count > 0:
                print(f"Added {creator_count} timelines where user {user_id} is the creator")
            
            # For SiteOwner (user ID 1), add access to all timelines
            if user_id == 1:
                cursor.execute("""
                    SELECT id as timeline_id, name as timeline_name, visibility, timeline_type, created_at
                    FROM timeline
                    WHERE id NOT IN (
                        SELECT timeline_id FROM timeline_member WHERE user_id = 1
                    ) AND id NOT IN (
                        SELECT id FROM timeline WHERE created_by = 1
                    )
                """)
                
                siteowner_count = 0
                for row in cursor.fetchall():
                    memberships.append({
                        'timeline_id': row['timeline_id'],
                        'timeline_name': row['timeline_name'],
                        'role': 'SiteOwner',
                        'is_active_member': True,
                        'isMember': True,
                        'joined_at': row['created_at'],
                        'timeline_visibility': row['visibility'],
                        'timeline_type': row['timeline_type'],
                        'is_site_owner': True
                    })
                    siteowner_count += 1
                
                if siteowner_count > 0:
                    print(f"Added {siteowner_count} timelines for SiteOwner access")
            
            # Update the user's passport with the latest membership data
            now = datetime.now().isoformat()
            cursor.execute(
                'UPDATE user_passport SET memberships_json = ?, last_updated = ? WHERE user_id = ?',
                (json.dumps(memberships), now, user_id)
            )
            
            # If no passport exists, create one
            if cursor.rowcount == 0:
                cursor.execute(
                    'INSERT INTO user_passport (user_id, memberships_json, last_updated) VALUES (?, ?, ?)',
                    (user_id, json.dumps(memberships), now)
                )
                print(f"Created new passport for user {user_id}")
            else:
                print(f"Updated existing passport for user {user_id}")
        
        # Commit all changes
        conn.commit()
        print("\nAll user passports have been updated successfully!")
        
        # Verify the fix
        print("\nVerifying fix...")
        for user_id in users:
            # Get the user's memberships from timeline_member
            cursor.execute("""
                SELECT timeline_id
                FROM timeline_member
                WHERE user_id = ? AND is_active_member = 1
            """, (user_id,))
            
            db_timeline_ids = set(row['timeline_id'] for row in cursor.fetchall())
            
            # Get the user's passport
            cursor.execute("SELECT memberships_json FROM user_passport WHERE user_id = ?", (user_id,))
            passport = cursor.fetchone()
            
            if passport:
                passport_memberships = json.loads(passport['memberships_json'])
                passport_timeline_ids = set(m['timeline_id'] for m in passport_memberships)
                
                # Check if all timeline_ids in the database are in the passport
                missing = db_timeline_ids - passport_timeline_ids
                if missing:
                    print(f"[WARNING] User {user_id} still missing timelines in passport: {missing}")
                else:
                    print(f"[OK] User {user_id} passport is now complete")
            else:
                print(f"[ERROR] User {user_id} has no passport record")
        
    except Exception as e:
        print(f"Error fixing passport sync: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    fix_passport_sync()
