import requests
import json
import sqlite3
import os
import jwt
from datetime import datetime, timedelta
import time

def get_token_for_user(user_id):
    """Generate a JWT token for testing"""
    # Connect to the database to get the username
    conn = sqlite3.connect('timeline_forum.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT username FROM user WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        print(f"Error: User with ID {user_id} not found in database")
        return None
    
    # Create a simple JWT token manually
    # Try to get the secret key from the app's config file
    try:
        from app import app
        secret_key = app.config.get('JWT_SECRET_KEY', 'dev-key-for-testing')
    except ImportError:
        # Fallback to environment variable or default
        secret_key = os.getenv('JWT_SECRET_KEY', 'dev-key-for-testing')
    
    payload = {
        "sub": str(user_id),
        "username": user['username'],
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token

def check_membership_status(user_id, timeline_id):
    """Check membership status for a user and timeline"""
    token = get_token_for_user(user_id)
    if not token:
        print(f"Error: User with ID {user_id} not found")
        return None
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"http://localhost:5000/api/v1/timelines/{timeline_id}/membership-status"
    print(f"\nChecking membership status for User ID: {user_id}, Timeline ID: {timeline_id}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            return data
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {str(e)}")
        return None

def join_community(user_id, timeline_id):
    """Test joining a community timeline"""
    token = get_token_for_user(user_id)
    if not token:
        print(f"Error: User with ID {user_id} not found")
        return None
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"http://localhost:5000/api/v1/timelines/{timeline_id}/access-requests"
    print(f"\nJoining community for User ID: {user_id}, Timeline ID: {timeline_id}")
    print(f"URL: {url}")
    
    try:
        response = requests.post(url, headers=headers, json={})
        print(f"Status Code: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            return data
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {str(e)}")
        return None

def check_database_membership(user_id, timeline_id):
    """Check the database directly for membership records"""
    conn = sqlite3.connect('timeline_forum.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT tm.id, tm.timeline_id, tm.user_id, tm.role, tm.is_active_member, 
               u.username, t.name as timeline_name
        FROM timeline_member tm
        JOIN user u ON tm.user_id = u.id
        JOIN timeline t ON tm.timeline_id = t.id
        WHERE tm.user_id = ? AND tm.timeline_id = ?
    """, (user_id, timeline_id))
    
    member = cursor.fetchone()
    conn.close()
    
    if member:
        print(f"\nDatabase record found for User ID: {user_id}, Timeline ID: {timeline_id}")
        print(f"Role: {member['role']}, Is Active: {member['is_active_member']}")
        return {
            "id": member['id'],
            "user_id": member['user_id'],
            "timeline_id": member['timeline_id'],
            "role": member['role'],
            "is_active_member": member['is_active_member']
        }
    else:
        print(f"\nNo database record found for User ID: {user_id}, Timeline ID: {timeline_id}")
        return None

def simulate_frontend_join_flow(user_id, timeline_id):
    """Simulate the frontend join flow with localStorage caching"""
    print(f"\n=== SIMULATING FRONTEND JOIN FLOW FOR USER {user_id} ON TIMELINE {timeline_id} ===")
    
    # Step 1: Check initial membership status
    print("\nStep 1: Check initial membership status")
    initial_status = check_membership_status(user_id, timeline_id)
    
    if initial_status and initial_status.get('is_member', False):
        print("User is already a member of this timeline. Test complete.")
        return
    
    # Step 2: Join the community
    print("\nStep 2: Join the community")
    join_result = join_community(user_id, timeline_id)
    
    if not join_result:
        print("Failed to join community. Test failed.")
        return
    
    # Step 3: Check membership status again after joining
    print("\nStep 3: Check membership status after joining")
    time.sleep(1)  # Wait a bit for the database to update
    after_join_status = check_membership_status(user_id, timeline_id)
    
    # Step 4: Verify database record
    print("\nStep 4: Verify database record")
    db_record = check_database_membership(user_id, timeline_id)
    
    # Step 5: Simulate localStorage caching
    print("\nStep 5: Simulate localStorage caching")
    local_storage_data = {
        "is_member": True,
        "role": join_result.get('role', 'member'),
        "timestamp": datetime.now().isoformat()
    }
    print(f"localStorage would contain: {json.dumps(local_storage_data, indent=2)}")
    
    # Step 6: Verify end-to-end flow
    print("\nStep 6: Verify end-to-end flow")
    success = (
        join_result and 
        after_join_status and 
        after_join_status.get('is_member', False) and
        db_record and 
        db_record.get('is_active_member', 0) == 1
    )
    
    if success:
        print("\n✅ TEST PASSED: Join community flow works correctly!")
        print(f"User {user_id} successfully joined timeline {timeline_id}")
        print(f"Role: {db_record.get('role', 'unknown')}")
        print(f"Membership status from API: {after_join_status.get('is_member')}")
    else:
        print("\n❌ TEST FAILED: Join community flow has issues")
        print("Check the logs above for details")

def test_multiple_users_and_timelines():
    """Test multiple users joining different types of timelines"""
    print("\n=== TESTING MULTIPLE USERS AND TIMELINES ===")
    
    # Test cases
    test_cases = [
        # Regular user joining public community
        {"user_id": 2, "timeline_id": 3, "description": "Regular user joining public community"},
        
        # Regular user joining private community
        {"user_id": 3, "timeline_id": 4, "description": "Regular user joining private community"},
        
        # Creator accessing their own timeline
        {"user_id": 4, "timeline_id": 5, "description": "Creator accessing their own timeline"}
    ]
    
    for case in test_cases:
        print(f"\n\n{'=' * 50}")
        print(f"TEST CASE: {case['description']}")
        print(f"{'=' * 50}")
        simulate_frontend_join_flow(case['user_id'], case['timeline_id'])

if __name__ == "__main__":
    print("=== TESTING JOIN COMMUNITY BUTTON FUNCTIONALITY ===")
    test_multiple_users_and_timelines()
