#!/usr/bin/env python3
"""
ONE-TIME-USE SCRIPT - SAFE TO DELETE

Test script for community timeline membership API endpoints.
Used for development and debugging purposes only.

Note: This is a one-time test script and can be safely deleted.
"""

import requests
import json
import sqlite3
import os
import jwt
from datetime import datetime, timedelta

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
    secret_key = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    payload = {
        "sub": str(user_id),
        "username": user['username'],
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token

def test_membership_status(user_id, timeline_id):
    """Test the membership status endpoint for a specific user and timeline"""
    token = get_token_for_user(user_id)
    if not token:
        print(f"Error: User with ID {user_id} not found")
        return
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"http://localhost:5000/api/v1/timelines/{timeline_id}/membership-status"
    print(f"\nTesting membership status for User ID: {user_id}, Timeline ID: {timeline_id}")
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Check if the user is a member
            is_member = data.get('is_member', False)
            role = data.get('role', None)
            
            print(f"Is Member: {is_member}")
            print(f"Role: {role}")
            
            return data
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {str(e)}")
        return None

def test_join_community(user_id, timeline_id):
    """Test joining a community timeline"""
    token = get_token_for_user(user_id)
    if not token:
        print(f"Error: User with ID {user_id} not found")
        return
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = f"http://localhost:5000/api/v1/timelines/{timeline_id}/access-requests"
    print(f"\nTesting join request for User ID: {user_id}, Timeline ID: {timeline_id}")
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

if __name__ == "__main__":
    print("=== TESTING MEMBERSHIP STATUS API ===")
    
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
        result = test_membership_status(case['user_id'], case['timeline_id'])
        
        if result:
            is_correct = result.get('is_member') == case['expected_member']
            status = "PASS" if is_correct else "FAIL"
            results.append({
                "case": case['description'],
                "status": status,
                "expected": case['expected_member'],
                "actual": result.get('is_member')
            })
        else:
            results.append({
                "case": case['description'],
                "status": "ERROR",
                "expected": case['expected_member'],
                "actual": None
            })
    
    # Test joining a community for TestUser3
    print("\n=== TESTING JOIN COMMUNITY ===")
    join_result = test_join_community(4, 3)  # TestUser3 joining Community Tech
    
    if join_result:
        # Check membership status after joining
        print("\n=== CHECKING MEMBERSHIP AFTER JOIN ===")
        updated_status = test_membership_status(4, 3)
        
        if updated_status:
            is_member_now = updated_status.get('is_member', False)
            results.append({
                "case": "TestUser3 joining public community",
                "status": "PASS" if is_member_now else "FAIL",
                "expected": True,
                "actual": is_member_now
            })
    
    # Print summary
    print("\n=== TEST RESULTS SUMMARY ===")
    for result in results:
        print(f"{result['status']}: {result['case']} - Expected: {result['expected']}, Actual: {result['actual']}")
    
    pass_count = sum(1 for r in results if r['status'] == 'PASS')
    fail_count = sum(1 for r in results if r['status'] == 'FAIL')
    error_count = sum(1 for r in results if r['status'] == 'ERROR')
    
    print(f"\nTotal: {len(results)}, Pass: {pass_count}, Fail: {fail_count}, Error: {error_count}")
