#!/usr/bin/env python3
"""
Test script to verify the user memberships endpoint and membership persistence.
This script tests the new /api/v1/user/memberships endpoint that returns all timeline memberships
for the current user.
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

def get_user_memberships(token):
    """Get all memberships for the current user"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_BASE_URL}/v1/user/memberships",
        headers=headers
    )
    
    if response.status_code != 200:
        print_error(f"Failed to get user memberships: {response.text}")
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

def get_timeline_members_from_db(timeline_id):
    """Get all members for a timeline directly from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT user_id, role, is_active_member, joined_at
        FROM timeline_member
        WHERE timeline_id = ?
    """, (timeline_id,))
    
    members = []
    for row in cursor.fetchall():
        members.append({
            "user_id": row[0],
            "role": row[1],
            "is_active_member": bool(row[2]),
            "joined_at": row[3]
        })
    
    conn.close()
    return members

def get_user_created_timelines_from_db(user_id):
    """Get all timelines created by a user directly from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, created_at
        FROM timeline
        WHERE created_by = ?
    """, (user_id,))
    
    timelines = []
    for row in cursor.fetchall():
        timelines.append({
            "id": row[0],
            "title": row[1],
            "created_at": row[2]
        })
    
    conn.close()
    return timelines

def verify_membership_consistency(user_id, api_memberships):
    """Verify that the API memberships match what's in the database"""
    print_header(f"Verifying membership consistency for user {user_id}")
    
    # Get timelines created by the user
    created_timelines = get_user_created_timelines_from_db(user_id)
    created_timeline_ids = set(t["id"] for t in created_timelines)
    print_info(f"User has created {len(created_timelines)} timelines: {created_timeline_ids}")
    
    # Get all timeline memberships for the user from the database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT timeline_id, role, is_active_member
        FROM timeline_member
        WHERE user_id = ? AND is_active_member = 1
    """, (user_id,))
    
    db_memberships = []
    for row in cursor.fetchall():
        db_memberships.append({
            "timeline_id": row[0],
            "role": row[1],
            "is_active_member": bool(row[2])
        })
    
    conn.close()
    
    # Convert API memberships to a comparable format
    api_membership_map = {m["timeline_id"]: m for m in api_memberships}
    api_timeline_ids = set(m["timeline_id"] for m in api_memberships)
    
    # Check if all created timelines are in the API response
    for timeline_id in created_timeline_ids:
        if timeline_id in api_timeline_ids:
            print_success(f"Created timeline {timeline_id} is correctly included in API response")
        else:
            print_error(f"Created timeline {timeline_id} is missing from API response")
    
    # Check if all active memberships from the database are in the API response
    for db_membership in db_memberships:
        timeline_id = db_membership["timeline_id"]
        if timeline_id in api_timeline_ids:
            api_role = api_membership_map[timeline_id]["role"]
            db_role = db_membership["role"]
            
            if api_role == db_role:
                print_success(f"Timeline {timeline_id} membership role matches: {api_role}")
            else:
                print_warning(f"Timeline {timeline_id} role mismatch: API={api_role}, DB={db_role}")
        else:
            print_error(f"Active membership for timeline {timeline_id} is missing from API response")
    
    # Check for any extra memberships in the API response
    extra_timelines = api_timeline_ids - created_timeline_ids - set(m["timeline_id"] for m in db_memberships)
    if user_id == 1:  # SiteOwner should have access to all timelines
        print_info(f"SiteOwner has {len(extra_timelines)} additional timelines (expected for SiteOwner)")
    elif extra_timelines:
        print_warning(f"API response includes {len(extra_timelines)} unexpected timeline memberships: {extra_timelines}")
    else:
        print_success("No unexpected timeline memberships in API response")

def main():
    print_header("User Memberships Test")
    
    # Test for each user
    for user_name, user_data in TEST_USERS.items():
        print_header(f"Testing user: {user_name} (ID: {user_data['id']})")
        
        # Login
        token = login_user(user_data["email"], user_data["password"])
        if not token:
            continue
        
        print_success(f"Successfully logged in as {user_name}")
        
        # Get user memberships
        memberships = get_user_memberships(token)
        if not memberships:
            continue
        
        print_success(f"Got {len(memberships)} memberships for {user_name}")
        print_info(json.dumps(memberships, indent=2))
        
        # Verify consistency with database
        verify_membership_consistency(user_data["id"], memberships)
        
        # Test a few specific timelines
        if memberships:
            # Test the first timeline from the memberships
            timeline_id = memberships[0]["timeline_id"]
            status = check_membership_status(token, timeline_id)
            if status:
                print_success(f"Membership status for timeline {timeline_id}: {status}")
                
                # Verify the status matches what's in the memberships list
                expected_is_member = True  # All memberships in the list should be active
                if status["is_member"] == expected_is_member:
                    print_success(f"Membership status matches expected value: {expected_is_member}")
                else:
                    print_error(f"Membership status mismatch: API={status['is_member']}, Expected={expected_is_member}")
    
    print_header("Test completed")

if __name__ == "__main__":
    main()
