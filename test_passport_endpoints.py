import requests
import json
import sys

def test_passport_endpoints():
    """
    Test the user passport endpoints to ensure they're working correctly.
    """
    # Base URL for API
    base_url = "http://localhost:5000/api"
    
    # Step 1: Login to get a token
    print("Step 1: Logging in to get a token...")
    login_data = {
        "email": "brahdyssey@gmail.com",
        "password": "password"  # Replace with actual password if different
    }
    
    try:
        login_response = requests.post(f"{base_url}/auth/login", json=login_data)
        login_response.raise_for_status()
        token = login_response.json().get("access_token")
        print(f"Login successful, received token: {token[:10]}...")
        
        # Set up headers with the token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Step 2: Test GET /api/v1/user/passport
        print("\nStep 2: Testing GET /api/v1/user/passport...")
        passport_response = requests.get(f"{base_url}/v1/user/passport", headers=headers)
        
        if passport_response.status_code == 200:
            print("GET /api/v1/user/passport successful!")
            passport_data = passport_response.json()
            print(f"Received passport data: {json.dumps(passport_data, indent=2)}")
        else:
            print(f"Error: GET /api/v1/user/passport failed with status code {passport_response.status_code}")
            print(f"Response: {passport_response.text}")
        
        # Step 3: Test POST /api/v1/user/passport/sync
        print("\nStep 3: Testing POST /api/v1/user/passport/sync...")
        sync_response = requests.post(f"{base_url}/v1/user/passport/sync", headers=headers)
        
        if sync_response.status_code == 200:
            print("POST /api/v1/user/passport/sync successful!")
            sync_data = sync_response.json()
            print(f"Received sync response: {json.dumps(sync_data, indent=2)}")
        else:
            print(f"Error: POST /api/v1/user/passport/sync failed with status code {sync_response.status_code}")
            print(f"Response: {sync_response.text}")
        
        # Step 4: Test GET /api/v1/timelines/{timeline_id}/membership-status
        print("\nStep 4: Testing GET /api/v1/timelines/1/membership-status...")
        timeline_id = 1  # Replace with an actual timeline ID if needed
        membership_response = requests.get(f"{base_url}/v1/timelines/{timeline_id}/membership-status", headers=headers)
        
        if membership_response.status_code == 200:
            print(f"GET /api/v1/timelines/{timeline_id}/membership-status successful!")
            membership_data = membership_response.json()
            print(f"Received membership data: {json.dumps(membership_data, indent=2)}")
        else:
            print(f"Error: GET /api/v1/timelines/{timeline_id}/membership-status failed with status code {membership_response.status_code}")
            print(f"Response: {membership_response.text}")
        
        print("\nAll tests completed!")
        
    except requests.exceptions.RequestException as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    test_passport_endpoints()
