"""
Simple test script to verify Cloudinary uploads are working correctly.
Run this script directly to test uploading a file to Cloudinary.
"""
import os
import sys
from cloud_storage import upload_file
import cloudinary

# Print Cloudinary configuration
print("Cloudinary Configuration:")
print(f"Cloud Name: {cloudinary.config().cloud_name}")
print(f"API Key: {cloudinary.config().api_key}")
print(f"Secure: {cloudinary.config().secure}")

def test_upload(file_path):
    """Test uploading a file to Cloudinary"""
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return False
    
    print(f"Uploading file: {file_path}")
    
    try:
        # Create a custom file-like object that has the filename attribute
        from werkzeug.datastructures import FileStorage
        
        # Open the file in binary mode
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Get the filename from the path
        filename = os.path.basename(file_path)
        
        # Create a FileStorage object that mimics a file upload
        file = FileStorage(
            stream=open(file_path, 'rb'),
            filename=filename,
            content_type=None  # Let Cloudinary detect the content type
        )
        
        print(f"Created FileStorage object with filename: {file.filename}")
        
        # Upload to Cloudinary
        result = upload_file(file, folder="test_uploads")
        
        # Print the result
        print("\nUpload successful!")
        print(f"Public ID: {result.get('public_id')}")
        print(f"URL: {result.get('url')}")
        print(f"Secure URL: {result.get('secure_url')}")
        
        return True
    except Exception as e:
        print(f"\nError uploading file: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Check if a file path was provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Use a default file from the uploads directory
        uploads_dir = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
        files = os.listdir(uploads_dir)
        if files:
            file_path = os.path.join(uploads_dir, files[0])
        else:
            print("Error: No files found in the uploads directory")
            sys.exit(1)
    
    # Test the upload
    success = test_upload(file_path)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
