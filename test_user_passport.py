#!/usr/bin/env python3
"""
Test script to verify the user passport system for membership persistence.
This script tests the new passport endpoints that provide persistent membership data
across devices and sessions.
"""

import os
import sys
import json
import sqlite3
import requests
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:5000/api"
DB_PATH = "timeline_forum.db"  # Match the database path used in app.py

# Test users (adjust these values as needed)
TEST_USERS = {
    "SiteOwner": {"email": "admin@example.com", "password": "password123", "id": 1},
    "TestUser1": {"email": "user1@example.com", "password": "password123", "id": 2},
    "TestUser2": {"email": "user2@example.com", "password": "password123", "id": 3},
    "TestUser3": {"email": "user3@example.com", "password": "password123", "id": 4},
}

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {text} ==={Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}[SUCCESS] {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}[ERROR] {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}[INFO] {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}[WARNING] {text}{Colors.ENDC}")

def login_user(email, password):
    """Login a user and return the access token"""
    print_info(f"Attempting to login user {email}")
    response = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    
    if response.status_code != 200:
        print_error(f"Failed to login user {email}: {response.text}")
        return None
    
    data = response.json()
    return data.get("access_token")

def get_user_passport(token):
    """Get the user's passport containing all memberships"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE_URL}/v1/user/passport",
        headers=headers
    )
    
    if response.status_code != 200:
        print_error(f"Failed to get user passport: {response.text}")
        return None
    
    return response.json()

def sync_user_passport(token):
    """Sync the user's passport with the latest membership data"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{API_BASE_URL}/v1/user/passport/sync",
        headers=headers
    )
    
    if response.status_code != 200:
        print_error(f"Failed to sync user passport: {response.text}")
        return None
    
    return response.json()

def check_membership_status(token, timeline_id):
    """Check membership status for a specific timeline"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE_URL}/v1/timelines/{timeline_id}/membership-status",
        headers=headers
    )
    
    if response.status_code != 200:
        print_error(f"Failed to check membership status for timeline {timeline_id}: {response.text}")
        return None
    
    return response.json()

def request_timeline_access(token, timeline_id):
    """Request access to a timeline (join a community)"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{API_BASE_URL}/v1/timelines/{timeline_id}/access-requests",
        headers=headers
    )
    
    if response.status_code != 200:
        print_error(f"Failed to request access to timeline {timeline_id}: {response.text}")
        return None
    
    return response.json()

def get_user_passport_from_db(user_id):
    """Get the user's passport directly from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM user_passport WHERE user_id = ?",
        (user_id,)
    )
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "user_id": row["user_id"],
        "memberships_json": json.loads(row["memberships_json"]),
        "last_updated": row["last_updated"]
    }

def test_passport_system():
    """Test the passport system for membership persistence"""
    print_header("TESTING USER PASSPORT SYSTEM")
    
    # 1. Login as TestUser1
    print_info("Step 1: Login as TestUser1")
    user = TEST_USERS["TestUser1"]
    token = login_user(user["email"], user["password"])
    
    if not token:
        print_error("Failed to login as TestUser1. Aborting test.")
        return
    
    print_success("Successfully logged in as TestUser1")
    
    # 2. Get the user's passport
    print_info("Step 2: Get TestUser1's passport")
    passport = get_user_passport(token)
    
    if not passport:
        print_error("Failed to get TestUser1's passport. Aborting test.")
        return
    
    print_success(f"Successfully retrieved TestUser1's passport")
    print_info(f"Passport contains {len(passport.get('memberships', []))} memberships")
    
    # 3. Find a community timeline that the user is not a member of
    print_info("Step 3: Finding a community timeline to join")
    
    # Connect to the database to find a suitable timeline
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Find community timelines that TestUser1 is not a member of
    cursor.execute("""
        SELECT t.id, t.name, t.visibility
        FROM timeline t
        WHERE t.timeline_type = 'community'
        AND t.visibility = 'public'
        AND t.id NOT IN (
            SELECT timeline_id FROM timeline_member WHERE user_id = ?
        )
        LIMIT 1
    """, (user["id"],))
    
    timeline = cursor.fetchone()
    conn.close()
    
    if not timeline:
        print_warning("No suitable community timeline found. Creating a test timeline...")
        # TODO: Create a test timeline if needed
        print_error("Test timeline creation not implemented. Aborting test.")
        return
    
    timeline_id = timeline[0]
    timeline_name = timeline[1]
    
    print_success(f"Found community timeline: {timeline_name} (ID: {timeline_id})")
    
    # 4. Check membership status for this timeline
    print_info(f"Step 4: Checking membership status for timeline {timeline_id}")
    status = check_membership_status(token, timeline_id)
    
    if not status:
        print_error(f"Failed to check membership status. Aborting test.")
        return
    
    if status.get("is_member"):
        print_warning(f"User is already a member of timeline {timeline_id}. This is unexpected.")
    else:
        print_success(f"User is not a member of timeline {timeline_id} as expected")
    
    # 5. Join the community timeline
    print_info(f"Step 5: Joining community timeline {timeline_id}")
    join_result = request_timeline_access(token, timeline_id)
    
    if not join_result:
        print_error(f"Failed to join timeline {timeline_id}. Aborting test.")
        return
    
    print_success(f"Successfully joined timeline {timeline_id}")
    
    # 6. Sync the user's passport
    print_info("Step 6: Syncing user passport after joining")
    sync_result = sync_user_passport(token)
    
    if not sync_result:
        print_error("Failed to sync user passport. Aborting test.")
        return
    
    print_success("Successfully synced user passport")
    
    # 7. Verify the passport contains the new membership
    print_info("Step 7: Verifying passport contains the new membership")
    updated_passport = get_user_passport(token)
    
    if not updated_passport:
        print_error("Failed to get updated passport. Aborting test.")
        return
    
    memberships = updated_passport.get("memberships", [])
    found_membership = False
    
    for membership in memberships:
        if membership.get("timeline_id") == timeline_id:
            found_membership = True
            print_success(f"Found membership for timeline {timeline_id} in passport")
            print_info(f"Role: {membership.get('role')}")
            break
    
    if not found_membership:
        print_error(f"Membership for timeline {timeline_id} not found in passport!")
    
    # 8. Verify the passport in the database
    print_info("Step 8: Verifying passport in database")
    db_passport = get_user_passport_from_db(user["id"])
    
    if not db_passport:
        print_error(f"No passport found in database for user {user['id']}. Aborting test.")
        return
    
    db_memberships = db_passport.get("memberships_json", [])
    found_in_db = False
    
    for membership in db_memberships:
        if membership.get("timeline_id") == timeline_id:
            found_in_db = True
            print_success(f"Found membership for timeline {timeline_id} in database passport")
            break
    
    if not found_in_db:
        print_error(f"Membership for timeline {timeline_id} not found in database passport!")
    
    # 9. Simulate logout and login (new session)
    print_info("Step 9: Simulating logout and login (new session)")
    token = login_user(user["email"], user["password"])
    
    if not token:
        print_error("Failed to login again as TestUser1. Aborting test.")
        return
    
    print_success("Successfully logged in again as TestUser1")
    
    # 10. Get the passport again and verify membership persists
    print_info("Step 10: Verifying membership persists after new login")
    new_passport = get_user_passport(token)
    
    if not new_passport:
        print_error("Failed to get passport after new login. Aborting test.")
        return
    
    new_memberships = new_passport.get("memberships", [])
    found_after_login = False
    
    for membership in new_memberships:
        if membership.get("timeline_id") == timeline_id:
            found_after_login = True
            print_success(f"Membership for timeline {timeline_id} persists after new login!")
            break
    
    if not found_after_login:
        print_error(f"Membership for timeline {timeline_id} not found after new login!")
    
    # Final result
    if found_membership and found_in_db and found_after_login:
        print_header("PASSPORT SYSTEM TEST PASSED!")
        print_success("The passport system is working correctly!")
    else:
        print_header("PASSPORT SYSTEM TEST FAILED!")
        print_error("The passport system is not working correctly.")

if __name__ == "__main__":
    test_passport_system()
