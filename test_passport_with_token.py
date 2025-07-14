import requests
import sys
import json

def test_passport_with_token():
    """
    Test the user passport endpoints with a valid JWT token.
    This script assumes you're already logged in to the frontend and have a valid token.
    """
    print("Testing User Passport Endpoints with Token")
    print("=========================================\n")
    
    # Ask for the token
    token = input("Please paste your JWT token from the browser (check localStorage): ")
    if not token:
        print("No token provided. Exiting.")
        sys.exit(1)
    
    # Base URL for API
    base_url = "http://localhost:5000/api"
    
    # Set up headers with the token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Test GET /api/v1/user/passport
    print("\nStep 1: Testing GET /api/v1/user/passport...")
    try:
        passport_response = requests.get(f"{base_url}/v1/user/passport", headers=headers)
        print(f"Status code: {passport_response.status_code}")
        
        if passport_response.status_code == 200:
            print("GET /api/v1/user/passport successful!")
            passport_data = passport_response.json()
            print(f"Received passport data: {json.dumps(passport_data, indent=2)}")
        else:
            print(f"Error: GET /api/v1/user/passport failed")
            print(f"Response: {passport_response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")
    
    # Test POST /api/v1/user/passport/sync
    print("\nStep 2: Testing POST /api/v1/user/passport/sync...")
    try:
        sync_response = requests.post(f"{base_url}/v1/user/passport/sync", headers=headers)
        print(f"Status code: {sync_response.status_code}")
        
        if sync_response.status_code == 200:
            print("POST /api/v1/user/passport/sync successful!")
            sync_data = sync_response.json()
            print(f"Received sync response: {json.dumps(sync_data, indent=2)}")
        else:
            print(f"Error: POST /api/v1/user/passport/sync failed")
            print(f"Response: {sync_response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")
    
    # Test GET /api/v1/timelines/1/membership-status
    print("\nStep 3: Testing GET /api/v1/timelines/1/membership-status...")
    try:
        timeline_id = 1  # Replace with an actual timeline ID if needed
        membership_response = requests.get(f"{base_url}/v1/timelines/{timeline_id}/membership-status", headers=headers)
        print(f"Status code: {membership_response.status_code}")
        
        if membership_response.status_code == 200:
            print(f"GET /api/v1/timelines/{timeline_id}/membership-status successful!")
            membership_data = membership_response.json()
            print(f"Received membership data: {json.dumps(membership_data, indent=2)}")
        else:
            print(f"Error: GET /api/v1/timelines/{timeline_id}/membership-status failed")
            print(f"Response: {membership_response.text}")
    except Exception as e:
        print(f"Exception: {str(e)}")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    test_passport_with_token()
