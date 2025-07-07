#!/usr/bin/env python3
"""
ONE-TIME-USE SCRIPT - SAFE TO DELETE

Diagnostic script to check membership records in the database.
Used for development and debugging purposes only.

Note: This is a one-time diagnostic script and can be safely deleted.
"""

import sqlite3
import json

def check_database_membership():
    """Check the database for membership records"""
    conn = sqlite3.connect('timeline_forum.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n=== DATABASE MEMBERSHIP RECORDS ===")
    
    # Check users
    print("\nUSERS:")
    cursor.execute("SELECT id, username, email FROM user")
    users = cursor.fetchall()
    for user in users:
        print(f"ID: {user['id']}, Username: {user['username']}, Email: {user['email']}")
    
    # Check timelines
    print("\nTIMELINES:")
    cursor.execute("SELECT id, name, timeline_type, visibility, created_by FROM timeline")
    timelines = cursor.fetchall()
    for timeline in timelines:
        print(f"ID: {timeline['id']}, Name: {timeline['name']}, Type: {timeline['timeline_type']}, " +
              f"Visibility: {timeline['visibility']}, Created by: {timeline['created_by']}")
    
    # Check timeline members
    print("\nTIMELINE MEMBERS:")
    cursor.execute("""
        SELECT tm.id, tm.timeline_id, tm.user_id, tm.role, tm.is_active_member, 
               u.username, t.name as timeline_name
        FROM timeline_member tm
        JOIN user u ON tm.user_id = u.id
        JOIN timeline t ON tm.timeline_id = t.id
    """)
    members = cursor.fetchall()
    for member in members:
        print(f"ID: {member['id']}, Timeline: {member['timeline_name']} (ID: {member['timeline_id']}), " +
              f"User: {member['username']} (ID: {member['user_id']}), Role: {member['role']}, " +
              f"Is Active: {member['is_active_member']}")
    
    # Check membership status for specific test cases
    print("\n=== MEMBERSHIP STATUS CHECKS ===")
    
    test_cases = [
        # SiteOwner should have access to all timelines
        {"user_id": 1, "timeline_id": 1, "expected_member": True, "description": "SiteOwner accessing hashtag timeline"},
        {"user_id": 1, "timeline_id": 3, "expected_member": True, "description": "SiteOwner accessing public community"},
        {"user_id": 1, "timeline_id": 4, "expected_member": True, "description": "SiteOwner accessing private community"},
        
        # TestUser1 is creator and admin of Community Tech
        {"user_id": 2, "timeline_id": 3, "expected_member": True, "description": "Creator accessing own community"},
        
        # TestUser2 is member of Community Tech, creator of Private Community
        {"user_id": 3, "timeline_id": 3, "expected_member": True, "description": "Member accessing community"},
        {"user_id": 3, "timeline_id": 4, "expected_member": True, "description": "Creator accessing own private community"},
        
        # TestUser3 is not a member of any community
        {"user_id": 4, "timeline_id": 3, "expected_member": False, "description": "Non-member accessing public community"},
        {"user_id": 4, "timeline_id": 4, "expected_member": False, "description": "Non-member accessing private community"}
    ]
    
    results = []
    
    for case in test_cases:
        user_id = case['user_id']
        timeline_id = case['timeline_id']
        
        print(f"\n--- {case['description']} ---")
        
        # Check if user exists
        cursor.execute("SELECT id, username FROM user WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            print(f"Error: User with ID {user_id} not found")
            results.append({
                "case": case['description'],
                "status": "ERROR",
                "error": f"User with ID {user_id} not found"
            })
            continue
        
        # Check if timeline exists
        cursor.execute("SELECT id, name, created_by FROM timeline WHERE id = ?", (timeline_id,))
        timeline = cursor.fetchone()
        if not timeline:
            print(f"Error: Timeline with ID {timeline_id} not found")
            results.append({
                "case": case['description'],
                "status": "ERROR",
                "error": f"Timeline with ID {timeline_id} not found"
            })
            continue
        
        # Check if user is creator
        is_creator = (user_id == timeline['created_by'])
        is_site_owner = (user_id == 1)
        
        # Check if user is a member
        cursor.execute("""
            SELECT id, role, is_active_member
            FROM timeline_member
            WHERE timeline_id = ? AND user_id = ?
        """, (timeline_id, user_id))
        membership = cursor.fetchone()
        
        # Determine membership status
        is_member = False
        role = None
        
        if membership:
            is_member = bool(membership['is_active_member'])
            role = membership['role']
            print(f"Found membership record: is_active_member={is_member}, role={role}")
        else:
            print("No membership record found")
        
        # Override for creator or site owner
        if is_creator:
            print(f"User is creator, should be considered a member")
            
        if is_site_owner:
            print(f"User is SiteOwner, should be considered a member")
        
        # According to the backend logic, creators and SiteOwner are always members
        final_is_member = is_member or is_creator or is_site_owner
        
        print(f"Final membership status: is_member={final_is_member}, role={role}")
        
        # Check if the result matches the expected value
        is_correct = final_is_member == case['expected_member']
        status = "PASS" if is_correct else "FAIL"
        
        results.append({
            "case": case['description'],
            "status": status,
            "expected": case['expected_member'],
            "actual": final_is_member,
            "role": role,
            "is_creator": is_creator,
            "is_site_owner": is_site_owner
        })
    
    # Print summary
    print("\n=== TEST RESULTS SUMMARY ===")
    for result in results:
        print(f"{result['status']}: {result['case']} - Expected: {result['expected']}, Actual: {result['actual']}")
        if result['is_creator']:
            print(f"  Note: User is the creator of this timeline")
        if result['is_site_owner']:
            print(f"  Note: User is the SiteOwner")
        if result['role']:
            print(f"  Role: {result['role']}")
    
    pass_count = sum(1 for r in results if r['status'] == 'PASS')
    fail_count = sum(1 for r in results if r['status'] == 'FAIL')
    error_count = sum(1 for r in results if r['status'] == 'ERROR')
    
    print(f"\nTotal: {len(results)}, Pass: {pass_count}, Fail: {fail_count}, Error: {error_count}")
    
    conn.close()

if __name__ == "__main__":
    check_database_membership()
