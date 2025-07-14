import sqlite3
import json
from datetime import datetime

def inspect_database():
    """Inspect the timeline_forum.db database to check users, memberships, and passport tables."""
    """
    Inspect the timeline_forum.db database to check membership and passport tables.
    """
    try:
        # Connect to the database
        conn = sqlite3.connect('timeline_forum.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check the user table first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if cursor.fetchone():
            print("[OK] user table exists")
            
            # Count records in user table
            cursor.execute("SELECT COUNT(*) as count FROM user")
            count = cursor.fetchone()['count']
            print(f"  - user table has {count} records")
            
            # Show all user records
            cursor.execute("SELECT id, username, email, created_at FROM user ORDER BY id")
            users = cursor.fetchall()
            print(f"  - User records:")
            for user in users:
                user_id = user['id']
                username = user['username']
                email = user['email']
                created_at = user['created_at']
                print(f"    User ID: {user_id}, Username: {username}, Email: {email}, Created: {created_at}")
        else:
            print("[MISSING] user table does not exist")
        
        # Check if user_passport table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
        if cursor.fetchone():
            print("[OK] user_passport table exists")
            
            # Count records in user_passport table
            cursor.execute("SELECT COUNT(*) as count FROM user_passport")
            count = cursor.fetchone()['count']
            print(f"  - user_passport table has {count} records")
            
            # Show all records from user_passport table with user info
            cursor.execute("""
                SELECT p.user_id, p.memberships_json, p.last_updated, u.username 
                FROM user_passport p
                JOIN user u ON p.user_id = u.id
                ORDER BY p.user_id
            """)
            passports = cursor.fetchall()
            print(f"  - All passport records:")
            for passport in passports:
                user_id = passport['user_id']
                username = passport['username']
                last_updated = passport['last_updated']
                try:
                    memberships = json.loads(passport['memberships_json'])
                    membership_count = len(memberships)
                except:
                    memberships = []
                    membership_count = 0
                print(f"    User ID: {user_id}, Username: {username}, Memberships: {membership_count}, Last Updated: {last_updated}")
                
                # Show details of each membership in the passport
                if membership_count > 0:
                    print(f"      Memberships in passport:")
                    for idx, membership in enumerate(memberships):
                        timeline_id = membership.get('timeline_id', 'Unknown')
                        timeline_name = membership.get('timeline_name', 'Unknown')
                        role = membership.get('role', 'Unknown')
                        is_member = membership.get('isMember', membership.get('is_active_member', False))
                        print(f"        {idx+1}. Timeline: {timeline_name} (ID: {timeline_id}), Role: {role}, Is Member: {is_member}")
                else:
                    print(f"      No memberships in passport")
        else:
            print("[MISSING] user_passport table does not exist")
        
        # Check if timeline_member table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timeline_member'")
        if cursor.fetchone():
            print("\n[OK] timeline_member table exists")
            
            # Count records in timeline_member table
            cursor.execute("SELECT COUNT(*) as count FROM timeline_member")
            count = cursor.fetchone()['count']
            print(f"  - timeline_member table has {count} records")
            
            # Show all records from timeline_member table with user info
            cursor.execute("""
                SELECT tm.user_id, tm.timeline_id, tm.role, tm.is_active_member, tm.joined_at, 
                       t.name as timeline_name, t.visibility, t.created_by,
                       u.username as username
                FROM timeline_member tm
                JOIN timeline t ON tm.timeline_id = t.id
                JOIN user u ON tm.user_id = u.id
                ORDER BY tm.user_id, tm.timeline_id
            """)
            members = cursor.fetchall()
            print(f"  - All membership records:")
            for member in members:
                user_id = member['user_id']
                username = member['username']
                timeline_id = member['timeline_id']
                role = member['role']
                is_active = member['is_active_member']
                timeline_name = member['timeline_name']
                created_by = member['created_by']
                is_creator = "Yes" if user_id == created_by else "No"
                print(f"    User ID: {user_id}, Username: {username}, Timeline: {timeline_name} (ID: {timeline_id}), Role: {role}, Active: {is_active}, Creator: {is_creator}")
        else:
            print("[MISSING] timeline_member table does not exist")
            
        # Check if timeline table exists and list community timelines
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timeline'")
        if cursor.fetchone():
            print("\n[OK] timeline table exists")
            
            # Count community timelines
            cursor.execute("SELECT COUNT(*) as count FROM timeline WHERE timeline_type = 'community'")
            count = cursor.fetchone()['count']
            print(f"  - Found {count} community timelines")
            
            # Show sample community timelines
            cursor.execute("""
                SELECT id, name, created_by, visibility, timeline_type
                FROM timeline 
                WHERE timeline_type = 'community'
                LIMIT 5
            """)
            timelines = cursor.fetchall()
            print(f"  - Sample community timelines:")
            for timeline in timelines:
                timeline_id = timeline['id']
                name = timeline['name']
                created_by = timeline['created_by']
                visibility = timeline['visibility']
                print(f"    ID: {timeline_id}, Name: {name}, Created By: {created_by}, Visibility: {visibility}")
        else:
            print("[MISSING] timeline table does not exist")
            
    except Exception as e:
        print(f"Error inspecting database: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    inspect_database()
