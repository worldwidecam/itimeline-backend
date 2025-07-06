import json
import sqlite3
from app import app, db, User, Timeline, TimelineMember

def print_db_contents():
    """Print the contents of the database tables for debugging"""
    conn = sqlite3.connect('timeline_forum.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n=== DATABASE CONTENTS ===")
    
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
    
    conn.close()

def test_membership_status_direct():
    """Test the membership status directly using the Flask app context"""
    print("\n=== TESTING MEMBERSHIP STATUS DIRECTLY ===")
    
    with app.app_context():
        # First, print the database contents
        print_db_contents()
        
        # Test cases based on our test data
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
            print(f"\n=== TEST CASE: {case['description']} ===")
            user_id = case['user_id']
            timeline_id = case['timeline_id']
            
            # Get the user and timeline
            user = User.query.get(user_id)
            timeline = Timeline.query.get(timeline_id)
            
            if not user:
                print(f"Error: User with ID {user_id} not found")
                results.append({
                    "case": case['description'],
                    "status": "ERROR",
                    "expected": case['expected_member'],
                    "actual": None,
                    "role": None,
                    "error": f"User with ID {user_id} not found"
                })
                continue
                
            if not timeline:
                print(f"Error: Timeline with ID {timeline_id} not found")
                results.append({
                    "case": case['description'],
                    "status": "ERROR",
                    "expected": case['expected_member'],
                    "actual": None,
                    "role": None,
                    "error": f"Timeline with ID {timeline_id} not found"
                })
                continue
            
            # Check if the user is a member
            is_site_owner = (user_id == 1)
            is_creator = (user_id == timeline.created_by)
            membership = TimelineMember.query.filter_by(timeline_id=timeline_id, user_id=user_id).first()
            
            # Implement the same logic as in the check_membership_status endpoint
            is_member = False
            role = None
            
            if membership:
                is_member = membership.is_active_member
                role = membership.role
                print(f"Found membership record: is_active_member={is_member}, role={role}")
            else:
                print("No membership record found")
                
                # If user is creator but no membership record exists, create one
                if is_creator:
                    print(f"User is creator but no membership record exists. Creating admin membership.")
                    membership = TimelineMember(
                        timeline_id=timeline_id,
                        user_id=user_id,
                        role='admin',
                        is_active_member=True
                    )
                    db.session.add(membership)
                    db.session.commit()
                    is_member = True
                    role = 'admin'
            
            # Override for creator or site owner
            if is_creator or is_site_owner:
                print(f"User is {'creator' if is_creator else 'SiteOwner'}, setting is_member=True")
                is_member = True
            
            print(f"Final result: is_member={is_member}, role={role}")
            
            # Check if the result matches the expected value
            is_correct = is_member == case['expected_member']
            status = "PASS" if is_correct else "FAIL"
            
            results.append({
                "case": case['description'],
                "status": status,
                "expected": case['expected_member'],
                "actual": is_member,
                "role": role
            })
        
        # Print summary
        print("\n=== TEST RESULTS SUMMARY ===")
        for result in results:
            print(f"{result['status']}: {result['case']} - Expected: {result['expected']}, Actual: {result['actual']}, Role: {result['role']}")
        
        pass_count = sum(1 for r in results if r['status'] == 'PASS')
        fail_count = sum(1 for r in results if r['status'] == 'FAIL')
        error_count = sum(1 for r in results if r['status'] == 'ERROR')
        
        print(f"\nTotal: {len(results)}, Pass: {pass_count}, Fail: {fail_count}, Error: {error_count}")

if __name__ == "__main__":
    test_membership_status_direct()
