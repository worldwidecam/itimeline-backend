import sqlite3
import json
from datetime import datetime

def inspect_database(db_path):
    """Inspect the specified database file to check users, memberships, and passport tables."""
    try:
        print(f"Inspecting database: {db_path}")
        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # List all tables in the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        print(f"\nFound {len(tables)} tables in the database:")
        for table in tables:
            table_name = table['name']
            # Skip sqlite internal tables
            if table_name.startswith('sqlite_'):
                continue
                
            # Get row count for the table
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                count = cursor.fetchone()['count']
                print(f"  - {table_name}: {count} records")
            except sqlite3.OperationalError as e:
                print(f"  - {table_name}: Error counting records - {str(e)}")
        
        # Check the user table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
        if cursor.fetchone():
            print("\n[OK] user table exists")
            
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
                email = user['email'] if 'email' in user.keys() else 'N/A'
                created_at = user['created_at'] if 'created_at' in user.keys() else 'N/A'
                print(f"    User ID: {user_id}, Username: {username}, Email: {email}, Created: {created_at}")
        else:
            print("\n[MISSING] user table does not exist")
        
        # Check if timeline table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timeline'")
        if cursor.fetchone():
            print("\n[OK] timeline table exists")
            
            # Count all timelines
            cursor.execute("SELECT COUNT(*) as count FROM timeline")
            count = cursor.fetchone()['count']
            print(f"  - Found {count} total timelines")
            
            # Try to get timeline_type column
            has_timeline_type = False
            cursor.execute("PRAGMA table_info(timeline)")
            columns = cursor.fetchall()
            for column in columns:
                if column['name'] == 'timeline_type':
                    has_timeline_type = True
                    break
            
            # Show all timelines
            if has_timeline_type:
                cursor.execute("""
                    SELECT id, name, created_by, visibility, timeline_type, created_at
                    FROM timeline
                    ORDER BY id
                """)
            else:
                cursor.execute("""
                    SELECT id, name, created_by, visibility, created_at
                    FROM timeline
                    ORDER BY id
                """)
                
            timelines = cursor.fetchall()
            print(f"  - All timelines:")
            for timeline in timelines:
                timeline_id = timeline['id']
                name = timeline['name']
                created_by = timeline['created_by']
                visibility = timeline['visibility'] if 'visibility' in timeline.keys() else 'N/A'
                timeline_type = timeline['timeline_type'] if has_timeline_type and 'timeline_type' in timeline.keys() else 'N/A'
                created_at = timeline['created_at'] if 'created_at' in timeline.keys() else 'N/A'
                print(f"    ID: {timeline_id}, Name: {name}, Created By: {created_by}, Type: {timeline_type}, Visibility: {visibility}, Created: {created_at}")
        else:
            print("\n[MISSING] timeline table does not exist")
            
        # Check if timeline_member table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timeline_member'")
        if cursor.fetchone():
            print("\n[OK] timeline_member table exists")
            
            # Count records in timeline_member table
            cursor.execute("SELECT COUNT(*) as count FROM timeline_member")
            count = cursor.fetchone()['count']
            print(f"  - timeline_member table has {count} records")
            
            # Show all records from timeline_member table
            try:
                cursor.execute("""
                    SELECT tm.user_id, tm.timeline_id, tm.role, tm.is_active_member, tm.joined_at
                    FROM timeline_member tm
                    ORDER BY tm.user_id, tm.timeline_id
                """)
                members = cursor.fetchall()
                print(f"  - All membership records:")
                for member in members:
                    user_id = member['user_id']
                    timeline_id = member['timeline_id']
                    role = member['role'] if 'role' in member.keys() else 'N/A'
                    is_active = member['is_active_member'] if 'is_active_member' in member.keys() else 'N/A'
                    joined_at = member['joined_at'] if 'joined_at' in member.keys() else 'N/A'
                    print(f"    User ID: {user_id}, Timeline ID: {timeline_id}, Role: {role}, Active: {is_active}, Joined: {joined_at}")
            except sqlite3.OperationalError as e:
                print(f"  - Error fetching membership records: {str(e)}")
        else:
            print("\n[MISSING] timeline_member table does not exist")
        
        # Check if user_passport table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
        if cursor.fetchone():
            print("\n[OK] user_passport table exists")
            
            # Count records in user_passport table
            cursor.execute("SELECT COUNT(*) as count FROM user_passport")
            count = cursor.fetchone()['count']
            print(f"  - user_passport table has {count} records")
            
            # Show all records from user_passport table
            cursor.execute("SELECT user_id, memberships_json, last_updated FROM user_passport ORDER BY user_id")
            passports = cursor.fetchall()
            print(f"  - All passport records:")
            for passport in passports:
                user_id = passport['user_id']
                last_updated = passport['last_updated'] if 'last_updated' in passport.keys() else 'N/A'
                try:
                    memberships = json.loads(passport['memberships_json'])
                    membership_count = len(memberships)
                except:
                    memberships = []
                    membership_count = 0
                print(f"    User ID: {user_id}, Memberships: {membership_count}, Last Updated: {last_updated}")
                
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
            print("\n[MISSING] user_passport table does not exist")
            
    except Exception as e:
        print(f"Error inspecting database: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    # Inspect all database files
    inspect_database('instance/itimeline.db')
    print("\n" + "="*50 + "\n")
    inspect_database('instance/timeline_forum.db')
    print("\n" + "="*50 + "\n")
    inspect_database('timeline_forum.db')
