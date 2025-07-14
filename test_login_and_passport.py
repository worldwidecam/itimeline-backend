import requests
import json
import sys
import time

def test_login_and_passport():
    """
    Test the login process and then test the passport endpoints with the obtained token.
    """
    print("Testing Login and User Passport Endpoints")
    print("=======================================\n")
    
    # Base URL for API
    base_url = "http://localhost:5000/api"
    
    # Step 1: Login to get a token
    print("Step 1: Logging in to get a token...")
    
    # Ask for credentials
    email = input("Enter your email: ")
    password = input("Enter your password: ")
    
    try:
        login_response = requests.post(f"{base_url}/auth/login", json={
            "email": email,
            "password": password
        })
        
        print(f"Login status code: {login_response.status_code}")
        
        if login_response.status_code != 200:
            print(f"Login failed: {login_response.text}")
            sys.exit(1)
        
        login_data = login_response.json()
        token = login_data.get("access_token")
        
        if not token:
            print("No token received in login response")
            print(f"Response: {json.dumps(login_data, indent=2)}")
            sys.exit(1)
        
        print("Login successful! Token obtained.")
        
        # Set up headers with the token
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Step 2: Test the test endpoint
        print("\nStep 2: Testing /api/test-passport...")
        try:
            test_response = requests.get(f"{base_url}/test-passport", headers=headers)
            print(f"Status code: {test_response.status_code}")
            
            if test_response.status_code == 200:
                print("Test endpoint successful!")
                print(f"Response: {json.dumps(test_response.json(), indent=2)}")
            else:
                print(f"Test endpoint failed: {test_response.text}")
        except Exception as e:
            print(f"Error calling test endpoint: {str(e)}")
        
        # Step 3: Test GET /api/v1/user/passport
        print("\nStep 3: Testing GET /api/v1/user/passport...")
        try:
            passport_response = requests.get(f"{base_url}/v1/user/passport", headers=headers)
            print(f"Status code: {passport_response.status_code}")
            
            if passport_response.status_code == 200:
                print("GET /api/v1/user/passport successful!")
                passport_data = passport_response.json()
                print(f"Received passport data: {json.dumps(passport_data, indent=2)}")
            else:
                print(f"GET /api/v1/user/passport failed: {passport_response.text}")
        except Exception as e:
            print(f"Error getting passport: {str(e)}")
        
        # Step 4: Test POST /api/v1/user/passport/sync
        print("\nStep 4: Testing POST /api/v1/user/passport/sync...")
        try:
            sync_response = requests.post(f"{base_url}/v1/user/passport/sync", headers=headers)
            print(f"Status code: {sync_response.status_code}")
            
            if sync_response.status_code == 200:
                print("POST /api/v1/user/passport/sync successful!")
                sync_data = sync_response.json()
                print(f"Received sync response: {json.dumps(sync_data, indent=2)}")
            else:
                print(f"POST /api/v1/user/passport/sync failed: {sync_response.text}")
        except Exception as e:
            print(f"Error syncing passport: {str(e)}")
        
        # Step 5: Test GET /api/v1/timelines/{timelineId}/membership-status
        print("\nStep 5: Testing GET /api/v1/timelines/{timelineId}/membership-status...")
        try:
            timeline_id = input("Enter a timeline ID to check membership status: ")
            membership_response = requests.get(f"{base_url}/v1/timelines/{timeline_id}/membership-status", headers=headers)
            print(f"Status code: {membership_response.status_code}")
            
            if membership_response.status_code == 200:
                print(f"GET /api/v1/timelines/{timeline_id}/membership-status successful!")
                membership_data = membership_response.json()
                print(f"Received membership data: {json.dumps(membership_data, indent=2)}")
            else:
                print(f"GET /api/v1/timelines/{timeline_id}/membership-status failed: {membership_response.text}")
        except Exception as e:
            print(f"Error checking membership: {str(e)}")
        
        print("\nAll tests completed!")
        
    except Exception as e:
        print(f"Error during testing: {str(e)}")

if __name__ == "__main__":
    test_login_and_passport()
