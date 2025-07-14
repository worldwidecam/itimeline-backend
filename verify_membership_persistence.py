"""
Verify membership persistence by checking the database structure and API endpoints.
"""
import sqlite3
import json
import os
from datetime import datetime

def verify_membership_persistence():
    """
    Check if the user_passport table exists and has the correct structure,
    and verify that the membership data is being stored correctly.
    """
    print("Verifying Membership Persistence")
    print("===============================\n")
    
    # Step 1: Check if user_passport table exists in both database files
    print("Step 1: Checking user_passport table in databases...")
    
    # Check production database (instance/timeline_forum.db)
    try:
        conn_prod = sqlite3.connect('instance/timeline_forum.db')
        conn_prod.row_factory = sqlite3.Row
        cursor_prod = conn_prod.cursor()
        
        # Check if user_passport table exists
        cursor_prod.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
        if cursor_prod.fetchone():
            print("[OK] user_passport table exists in production database")
            
            # Check table structure
            cursor_prod.execute("PRAGMA table_info(user_passport)")
            columns = cursor_prod.fetchall()
            column_names = [col['name'] for col in columns]
            
            expected_columns = ['user_id', 'memberships_json', 'last_updated']
            missing_columns = [col for col in expected_columns if col not in column_names]
            
            if not missing_columns:
                print("[OK] user_passport table has the correct structure")
            else:
                print(f"[WARNING] user_passport table is missing columns: {missing_columns}")
            
            # Check if there's any data
            cursor_prod.execute("SELECT COUNT(*) FROM user_passport")
            count = cursor_prod.fetchone()[0]
            print(f"[INFO] Found {count} records in user_passport table")
            
            if count > 0:
                # Get a sample record
                cursor_prod.execute("SELECT * FROM user_passport LIMIT 1")
                sample = cursor_prod.fetchone()
                print(f"[INFO] Sample record: {dict(sample)}")
                
                # Parse the memberships_json to check its structure
                try:
                    memberships = json.loads(sample['memberships_json'])
                    print(f"[INFO] Sample record has {len(memberships)} memberships")
                    
                    if memberships:
                        print(f"[INFO] Sample membership: {memberships[0]}")
                        
                        # Check if the membership has the required fields
                        required_fields = ['timeline_id', 'role', 'is_active_member', 'timeline_name']
                        missing_fields = [field for field in required_fields if field not in memberships[0]]
                        
                        if not missing_fields:
                            print("[OK] Membership data has the correct structure")
                        else:
                            print(f"[WARNING] Membership data is missing fields: {missing_fields}")
                except json.JSONDecodeError:
                    print("[ERROR] Failed to parse memberships_json")
        else:
            print("[ERROR] user_passport table does not exist in production database")
    except Exception as e:
        print(f"[ERROR] Failed to check production database: {str(e)}")
    finally:
        if 'conn_prod' in locals():
            conn_prod.close()
    
    # Step 2: Check if timeline_member table has correct data
    print("\nStep 2: Checking timeline_member table...")
    try:
        conn = sqlite3.connect('instance/timeline_forum.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if timeline_member table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timeline_member'")
        if cursor.fetchone():
            print("[OK] timeline_member table exists")
            
            # Get count of active members
            cursor.execute("SELECT COUNT(*) FROM timeline_member WHERE is_active_member = 1")
            active_count = cursor.fetchone()[0]
            print(f"[INFO] Found {active_count} active members in timeline_member table")
            
            # Get sample timeline memberships
            cursor.execute("""
                SELECT tm.timeline_id, tm.user_id, tm.role, tm.is_active_member, t.name as timeline_name
                FROM timeline_member tm
                JOIN timeline t ON tm.timeline_id = t.id
                WHERE tm.is_active_member = 1
                LIMIT 5
            """)
            members = cursor.fetchall()
            
            if members:
                print("[INFO] Sample timeline memberships:")
                for member in members:
                    print(f"  - Timeline {member['timeline_id']} ({member['timeline_name']}): User {member['user_id']} is {member['role']}")
            else:
                print("[WARNING] No active timeline memberships found")
        else:
            print("[ERROR] timeline_member table does not exist")
    except Exception as e:
        print(f"[ERROR] Failed to check timeline_member table: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()
    
    # Step 3: Check if the passport sync function is working correctly
    print("\nStep 3: Verifying passport sync function...")
    try:
        # Connect to the database
        conn = sqlite3.connect('instance/timeline_forum.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get a user with timeline memberships
        cursor.execute("""
            SELECT DISTINCT user_id 
            FROM timeline_member 
            WHERE is_active_member = 1 
            LIMIT 1
        """)
        user_row = cursor.fetchone()
        
        if user_row:
            user_id = user_row['user_id']
            print(f"[INFO] Testing with user_id: {user_id}")
            
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
                    'role': row['role'],
                    'is_active_member': bool(row['is_active_member']),
                    'isMember': bool(row['is_active_member']),
                    'joined_at': row['joined_at'],
                    'timeline_name': row['timeline_name'],
                    'visibility': row['visibility'],
                    'timeline_type': row['timeline_type']
                })
            
            print(f"[INFO] Found {len(memberships)} memberships for user {user_id}")
            
            # Check if the user has a passport
            cursor.execute("SELECT * FROM user_passport WHERE user_id = ?", (user_id,))
            passport = cursor.fetchone()
            
            if passport:
                print("[OK] User has a passport record")
                
                # Parse the memberships from the passport
                try:
                    passport_memberships = json.loads(passport['memberships_json'])
                    print(f"[INFO] Passport has {len(passport_memberships)} memberships")
                    
                    # Compare the memberships from timeline_member with the passport
                    timeline_ids_in_db = set(m['timeline_id'] for m in memberships)
                    timeline_ids_in_passport = set(m['timeline_id'] for m in passport_memberships)
                    
                    missing_in_passport = timeline_ids_in_db - timeline_ids_in_passport
                    extra_in_passport = timeline_ids_in_passport - timeline_ids_in_db
                    
                    if not missing_in_passport and not extra_in_passport:
                        print("[OK] Passport memberships match database memberships")
                    else:
                        if missing_in_passport:
                            print(f"[WARNING] Memberships missing in passport: {missing_in_passport}")
                        if extra_in_passport:
                            print(f"[WARNING] Extra memberships in passport: {extra_in_passport}")
                except json.JSONDecodeError:
                    print("[ERROR] Failed to parse passport memberships_json")
            else:
                print("[WARNING] User does not have a passport record")
        else:
            print("[WARNING] No users with active memberships found")
    except Exception as e:
        print(f"[ERROR] Failed to verify passport sync: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()
    
    print("\nMembership persistence verification complete!")

if __name__ == "__main__":
    verify_membership_persistence()
