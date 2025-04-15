import requests
import os
import sys

def test_upload_endpoint(file_path, endpoint):
    """
    Test the upload endpoint with a file
    
    Args:
        file_path: Path to the file to upload
        endpoint: API endpoint to test ('/api/upload' or '/api/upload-media')
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
    
    # API URL
    api_url = f"http://localhost:5000{endpoint}"
    
    print(f"Testing upload to {api_url}")
    print(f"File: {file_path}")
    
    # Open the file
    with open(file_path, 'rb') as f:
        # Create the files dict for the request
        files = {'file': (os.path.basename(file_path), f)}
        
        # Make the request
        try:
            response = requests.post(api_url, files=files)
            
            # Print the response
            print(f"\nResponse status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("Upload successful!")
                print(f"URL: {data.get('url')}")
                print(f"Storage: {data.get('storage', 'unknown')}")
                print(f"Type: {data.get('type')}")
                print("\nFull response data:")
                import json
                print(json.dumps(data, indent=2))
            else:
                print(f"Upload failed: {response.text}")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Check if a file path was provided
    if len(sys.argv) < 2:
        print("Usage: python test_upload_endpoint.py <file_path> [endpoint]")
        print("Example: python test_upload_endpoint.py test.jpg /api/upload-media")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Default endpoint is /api/upload-media
    endpoint = sys.argv[2] if len(sys.argv) > 2 else "/api/upload-media"
    
    test_upload_endpoint(file_path, endpoint)
