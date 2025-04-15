import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
import mimetypes

upload_bp = Blueprint('upload', __name__)

# Expanded allowed extensions to include various media types
ALLOWED_EXTENSIONS = {
    # Images
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg',
    # Videos
    'mp4', 'webm', 'ogg', 'mov', 'avi', 'wmv', 'flv', 'mkv',
    # Audio
    'mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a'
}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_unique_filename(filename):
    """Generate a unique filename while preserving the original extension."""
    ext = filename.rsplit('.', 1)[1].lower()
    return f"{uuid.uuid4()}.{ext}"

def get_media_type(filename):
    """Determine the media type based on file extension."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'

@upload_bp.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Upload a file to Cloudinary and return the URL.
    This endpoint is used for all media uploads in the application.
    """
    print("\n===== CLOUDINARY UPLOAD REQUEST RECEIVED =====")
    
    if 'file' not in request.files:
        print("ERROR: No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        print("ERROR: No selected file (empty filename)")
        return jsonify({'error': 'No selected file'}), 400
    
    print(f"File received: {file.filename}")
    print(f"Content-Type: {file.content_type}")
    
    if file and allowed_file(file.filename):
        try:
            # Determine the appropriate folder based on content type
            folder = "timeline_media"  # Default folder for timeline media
            
            # Import the Cloudinary upload function
            from cloud_storage import upload_file as cloudinary_upload_file
            
            # Upload to Cloudinary
            print(f"Uploading to Cloudinary in folder: {folder}")
            upload_result = cloudinary_upload_file(file, folder=folder)
            
            print("Cloudinary upload result:")
            print(f"  Success: {upload_result.get('success', False)}")
            print(f"  Public ID: {upload_result.get('public_id')}")
            print(f"  URL: {upload_result.get('url')}")
            
            # Check if the upload was successful
            if not upload_result.get('success', False):
                print(f"ERROR: Cloudinary upload failed: {upload_result.get('error')}")
                return jsonify({
                    'error': f"Cloudinary upload failed: {upload_result.get('error')}"
                }), 500
            
            # Get the URL from the result
            cloudinary_url = upload_result.get('url')
            if not cloudinary_url:
                print("ERROR: No URL returned from Cloudinary")
                return jsonify({'error': 'No URL returned from Cloudinary'}), 500
            
            # Return the Cloudinary URL and metadata
            response_data = {
                'url': cloudinary_url,
                'filename': file.filename,
                'public_id': upload_result.get('public_id'),
                'resource_type': upload_result.get('resource_type', 'image'),
                'type': file.content_type,
                'storage': 'cloudinary'
            }
            
            print(f"Response data: {response_data}")
            print("===== CLOUDINARY UPLOAD COMPLETED SUCCESSFULLY =====\n")
            
            return jsonify(response_data)
            
        except Exception as e:
            print(f"ERROR uploading to Cloudinary: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return jsonify({'error': f'Failed to upload file: {str(e)}'}), 500
    
    print(f"ERROR: File type not allowed for {file.filename}")
    return jsonify({'error': 'File type not allowed'}), 400

@upload_bp.route('/api/upload-media', methods=['POST'])
def upload_media():
    """Upload media files for timeline events"""
    """
    Endpoint specifically for uploading media files (images, videos, audio).
    Returns more detailed information about the media type.
    """
    print("\n===== MEDIA UPLOAD REQUEST RECEIVED =====")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request form data: {request.form}")
    print(f"Request files: {request.files.keys()}")
    
    # Check if the file part exists in the request
    if 'file' not in request.files:
        print("ERROR: No file part in request")
        return jsonify({
            'error': 'No file part', 
            'message': 'The request does not contain a file part',
            'request_keys': list(request.files.keys())
        }), 400
    
    file = request.files['file']
    
    # Check if a file was actually selected
    if file.filename == '':
        print("ERROR: No selected file (empty filename)")
        return jsonify({'error': 'No selected file', 'message': 'No file was selected'}), 400
    
    print(f"File received: {file.filename}")
    print(f"Content-Type: {file.content_type}")
    print(f"File size: {file.content_length if hasattr(file, 'content_length') else 'unknown'} bytes")
    
    # Validate file type
    if not allowed_file(file.filename):
        print(f"ERROR: File type not allowed for {file.filename}")
        return jsonify({
            'error': 'File type not allowed', 
            'message': f'The file type of {file.filename} is not allowed',
            'allowed_extensions': list(ALLOWED_EXTENSIONS)
        }), 400
    
    try:
        # Secure the filename and generate a unique name
        filename = secure_filename(file.filename)
        unique_filename = get_unique_filename(filename)
        print(f"Secured filename: {filename}")
        print(f"Generated unique filename: {unique_filename}")
        
        # Ensure upload directory exists
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        print(f"Upload folder: {upload_folder}")
        print(f"Upload folder exists: {os.path.exists(upload_folder)}")
        print(f"Upload folder permissions: {oct(os.stat(upload_folder).st_mode)[-3:]}")
        
        # Create the full file path
        file_path = os.path.join(upload_folder, unique_filename)
        print(f"Target file path: {file_path}")
        
        # Save the file
        try:
            file.save(file_path)
            # Verify the file was saved
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                print(f"File saved successfully at: {file_path}")
                print(f"File size: {file_size} bytes ({file_size/1024:.2f} KB)")
            else:
                print(f"ERROR: File was not saved at {file_path} (file does not exist after save)")
                return jsonify({'error': 'File was not saved', 'message': 'The file was not saved properly'}), 500
        except Exception as e:
            print(f"ERROR saving file: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return jsonify({'error': 'Failed to save file', 'message': str(e)}), 500
        
        # Determine media type
        media_type = get_media_type(filename)
        media_category = 'other'
        
        if media_type.startswith('image/'):
            media_category = 'image'
        elif media_type.startswith('video/'):
            media_category = 'video'
        elif media_type.startswith('audio/'):
            media_category = 'audio'
        
        print(f"Media type: {media_type}")
        print(f"Media category: {media_category}")
        
        # First try to upload to Cloudinary BEFORE saving locally
        cloudinary_success = False
        cloudinary_url = None
        cloudinary_public_id = None
        
        try:
            # Import the Cloudinary upload function
            from cloud_storage import upload_file as cloudinary_upload_file
            
            # Create a copy of the file to upload to Cloudinary
            # This is necessary because we need to reset the file pointer
            file.seek(0)  # Reset file pointer to beginning
            
            # Upload to Cloudinary
            print(f"Attempting to upload to Cloudinary first")
            upload_result = cloudinary_upload_file(file, folder="timeline_media")
            
            if upload_result.get('success'):
                print("Cloudinary upload successful:")
                print(f"  Public ID: {upload_result.get('public_id')}")
                print(f"  URL: {upload_result.get('url')}")
                
                # Store Cloudinary information
                cloudinary_success = True
                cloudinary_url = upload_result.get('url')
                cloudinary_public_id = upload_result.get('public_id')
                
                # Reset file pointer for local save
                file.seek(0)
            else:
                print(f"WARNING: Cloudinary upload returned error: {upload_result.get('error')}")
        except Exception as cloud_error:
            print(f"WARNING: Cloudinary upload failed: {str(cloud_error)}")
            import traceback
            print(traceback.format_exc())
        
        # Create the response data
        if cloudinary_success and cloudinary_url:
            response_data = {
                'url': cloudinary_url,  # Use URL from Cloudinary
                'filename': unique_filename,
                'type': media_type,
                'category': media_category,
                'size': file_size,
                'size_kb': f"{file_size/1024:.2f} KB",
                'cloudinary_id': cloudinary_public_id,
                'local_path': f'/static/uploads/{unique_filename}',
                'storage': 'cloudinary'
            }
            print("Using Cloudinary URL in response")
        else:
            # If Cloudinary failed, use local file path
            response_data = {
                'url': f'/static/uploads/{unique_filename}',
                'filename': unique_filename,
                'type': media_type,
                'category': media_category,
                'size': file_size,
                'size_kb': f"{file_size/1024:.2f} KB",
                'full_path': file_path,
                'server_path': f'/static/uploads/{unique_filename}',
                'storage': 'local'
            }
            print("Using local file path in response")
        
        print(f"Response data: {response_data}")
        print("===== MEDIA UPLOAD COMPLETED SUCCESSFULLY =====\n")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"UNEXPECTED ERROR during upload process: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': 'Server error', 'message': str(e)}), 500
