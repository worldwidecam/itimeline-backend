"""
Test script for community timeline membership integration

This script tests the community timeline membership API endpoints
and verifies that the backend is correctly handling member roles,
permissions, and special cases like SiteOwner and creator access.
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:5000/api/v1"
TEST_USER_ID = 2  # Regular test user (not SiteOwner)
ADMIN_USER_ID = 1  # SiteOwner (ID 1)
TEST_TIMELINE_ID = None  # Will be set after timeline creation

# Mock JWT tokens for authentication (replace with actual tokens in production)
# In a real scenario, you would get these by authenticating
ADMIN_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTY4ODU3NjQ2MSwianRpIjoiMmEzYzVkM2EtYWJjZC00ZWZnLWhpamstbG1ub3BxcnN0dXYiLCJ0eXBlIjoiYWNjZXNzIiwic3ViIjoxLCJuYmYiOjE2ODg1NzY0NjEsImV4cCI6MTY4ODU4MDA2MX0.fake_signature"
USER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTY4ODU3NjQ2MSwianRpIjoiMmEzYzVkM2EtYWJjZC00ZWZnLWhpamstbG1ub3BxcnN0dXYiLCJ0eXBlIjoiYWNjZXNzIiwic3ViIjoyLCJuYmYiOjE2ODg1NzY0NjEsImV4cCI6MTY4ODU4MDA2MX0.fake_signature"

# Headers for API requests
ADMIN_HEADERS = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}

USER_HEADERS = {
    "Authorization": f"Bearer {USER_TOKEN}",
    "Content-Type": "application/json"
}

def print_separator():
    """Print a separator line for better readability"""
    print("\n" + "-" * 80 + "\n")

def create_test_timeline():
    """Create a test community timeline"""
    global TEST_TIMELINE_ID
    
    print("Creating test community timeline...")
    
    # Generate a unique name using timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    timeline_name = f"test-community-{timestamp}"
    
    data = {
        "name": timeline_name,
        "description": "Test community timeline for membership integration testing",
        "timeline_type": "community",
        "visibility": "public"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/timelines/community",
            headers=ADMIN_HEADERS,
            json=data
        )
        
        if response.status_code == 201:
            result = response.json()
            TEST_TIMELINE_ID = result.get("id")
            print(f"✅ Timeline created successfully with ID: {TEST_TIMELINE_ID}")
            print(f"Timeline details: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Failed to create timeline: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception while creating timeline: {str(e)}")
        return False

def test_get_members():
    """Test getting the members of the timeline"""
    print("Testing get members endpoint...")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/timelines/{TEST_TIMELINE_ID}/members",
            headers=ADMIN_HEADERS
        )
        
        if response.status_code == 200:
            members = response.json()
            print(f"✅ Got {len(members)} members successfully")
            print(f"Members: {json.dumps(members, indent=2)}")
            
            # Verify that the creator is in the members list with Admin role
            creator_found = False
            for member in members:
                if member.get("user_id") == ADMIN_USER_ID:
                    creator_found = True
                    if member.get("role").lower() == "admin":
                        print("✅ Creator is correctly listed as Admin")
                    else:
                        print(f"❌ Creator has incorrect role: {member.get('role')}")
            
            if not creator_found:
                print("❌ Creator not found in members list")
                
            return True
        else:
            print(f"❌ Failed to get members: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception while getting members: {str(e)}")
        return False

def test_add_member():
    """Test adding a new member to the timeline"""
    print("Testing add member endpoint...")
    
    data = {
        "user_id": TEST_USER_ID,
        "role": "member"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/timelines/{TEST_TIMELINE_ID}/members",
            headers=ADMIN_HEADERS,
            json=data
        )
        
        if response.status_code == 201:
            result = response.json()
            print(f"✅ Member added successfully")
            print(f"Member details: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Failed to add member: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception while adding member: {str(e)}")
        return False

def test_update_member_role():
    """Test updating a member's role"""
    print("Testing update member role endpoint...")
    
    data = {
        "role": "moderator"
    }
    
    try:
        response = requests.put(
            f"{API_BASE_URL}/timelines/{TEST_TIMELINE_ID}/members/{TEST_USER_ID}/role",
            headers=ADMIN_HEADERS,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Member role updated successfully")
            print(f"Updated member details: {json.dumps(result, indent=2)}")
            
            # Verify the role was updated correctly
            if result.get("role").lower() == "moderator":
                print("✅ Role correctly updated to moderator")
            else:
                print(f"❌ Role not updated correctly: {result.get('role')}")
                
            return True
        else:
            print(f"❌ Failed to update member role: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception while updating member role: {str(e)}")
        return False

def test_membership_status():
    """Test checking membership status"""
    print("Testing membership status endpoint...")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/timelines/{TEST_TIMELINE_ID}/membership-status",
            headers=USER_HEADERS
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Membership status checked successfully")
            print(f"Status: {json.dumps(result, indent=2)}")
            
            # Verify the status is correct
            if result.get("is_member") == True:
                print("✅ User is correctly identified as a member")
            else:
                print("❌ User is not identified as a member")
                
            if result.get("role").lower() == "moderator":
                print("✅ User role is correctly identified as moderator")
            else:
                print(f"❌ User role is incorrect: {result.get('role')}")
                
            return True
        else:
            print(f"❌ Failed to check membership status: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception while checking membership status: {str(e)}")
        return False

def test_remove_member():
    """Test removing a member from the timeline"""
    print("Testing remove member endpoint...")
    
    try:
        response = requests.delete(
            f"{API_BASE_URL}/timelines/{TEST_TIMELINE_ID}/members/{TEST_USER_ID}",
            headers=ADMIN_HEADERS
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Member removed successfully")
            print(f"Result: {json.dumps(result, indent=2)}")
            return True
        else:
            print(f"❌ Failed to remove member: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Exception while removing member: {str(e)}")
        return False

def test_special_cases():
    """Test special cases like SiteOwner protection"""
    print("Testing special cases...")
    
    # Try to remove SiteOwner (should fail)
    print("Attempting to remove SiteOwner (should fail)...")
    try:
        response = requests.delete(
            f"{API_BASE_URL}/timelines/{TEST_TIMELINE_ID}/members/1",
            headers=USER_HEADERS
        )
        
        if response.status_code != 200:
            print(f"✅ Correctly prevented removing SiteOwner: {response.status_code}")
            print(f"Error message: {response.text}")
        else:
            print("❌ Failed test: Was able to remove SiteOwner")
            
    except Exception as e:
        print(f"❌ Exception while testing SiteOwner removal: {str(e)}")
    
    # Try to demote SiteOwner (should fail)
    print("\nAttempting to demote SiteOwner (should fail)...")
    try:
        response = requests.put(
            f"{API_BASE_URL}/timelines/{TEST_TIMELINE_ID}/members/1/role",
            headers=USER_HEADERS,
            json={"role": "member"}
        )
        
        if response.status_code != 200:
            print(f"✅ Correctly prevented demoting SiteOwner: {response.status_code}")
            print(f"Error message: {response.text}")
        else:
            print("❌ Failed test: Was able to demote SiteOwner")
            
    except Exception as e:
        print(f"❌ Exception while testing SiteOwner demotion: {str(e)}")

def run_all_tests():
    """Run all tests in sequence"""
    print_separator()
    print("STARTING COMMUNITY TIMELINE MEMBERSHIP INTEGRATION TESTS")
    print_separator()
    
    # Create test timeline
    if not create_test_timeline():
        print("❌ Failed to create test timeline. Aborting tests.")
        return
    
    print_separator()
    
    # Test getting members (should include creator)
    test_get_members()
    
    print_separator()
    
    # Test adding a member
    test_add_member()
    
    print_separator()
    
    # Test getting members again (should include new member)
    test_get_members()
    
    print_separator()
    
    # Test updating member role
    test_update_member_role()
    
    print_separator()
    
    # Test checking membership status
    test_membership_status()
    
    print_separator()
    
    # Test special cases
    test_special_cases()
    
    print_separator()
    
    # Test removing a member
    test_remove_member()
    
    print_separator()
    
    # Test getting members one last time (should not include removed member)
    test_get_members()
    
    print_separator()
    print("ALL TESTS COMPLETED")
    print_separator()

if __name__ == "__main__":
    run_all_tests()
