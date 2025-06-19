from app import app, User, create_access_token
import json

# This script generates a JWT token directly using the Flask app context
# It's a one-time-use script that can be deleted after obtaining the token

with app.app_context():
    # Get the user with ID 1 (Brahdyssey)
    user = User.query.get(1)
    
    if user:
        # Create an access token for the user
        access_token = create_access_token(identity=user.id)
        
        print(f"User: {user.username} (ID: {user.id})")
        print(f"Access Token: {access_token}")
        
        # Print a curl command that can be used to test the members endpoint
        print("\nTest command for members endpoint:")
        print(f'curl -H "Authorization: Bearer {access_token}" http://localhost:5000/api/v1/timelines/1/members')
    else:
        print("User not found!")
