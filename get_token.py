import requests
import json

# Login endpoint
url = "http://localhost:5000/api/auth/login"

# Login credentials - using the user we found in the database
data = {
    "email": "brahdyssey@gmail.com",
    "password": "password"  # This is a guess, you might need to update this
}

# Make the request
response = requests.post(url, json=data)

# Print the response
print(f"Status Code: {response.status_code}")
print("Response:")
try:
    print(json.dumps(response.json(), indent=4))
except:
    print(response.text)

# Note: This is a one-time-use script that can be deleted after obtaining the token
