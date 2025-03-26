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
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = get_unique_filename(filename)
        
        # Ensure upload directory exists
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # Return the URL path to the uploaded file
        return jsonify({
            'url': f'/static/uploads/{unique_filename}',
            'filename': unique_filename
        })
    
    return jsonify({'error': 'File type not allowed'}), 400

@upload_bp.route('/api/upload-media', methods=['POST'])
def upload_media():
    """
    Endpoint specifically for uploading media files (images, videos, audio).
    Returns more detailed information about the media type.
    """
    print("=== MEDIA UPLOAD REQUEST RECEIVED ===")
    
    if 'file' not in request.files:
        print("ERROR: No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        print("ERROR: No selected file (empty filename)")
        return jsonify({'error': 'No selected file'}), 400
    
    print(f"File received: {file.filename}, Content-Type: {file.content_type}")
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = get_unique_filename(filename)
        print(f"Secured filename: {filename}")
        print(f"Generated unique filename: {unique_filename}")
        
        # Ensure upload directory exists
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        print(f"Upload folder: {upload_folder}")
        print(f"Upload folder exists: {os.path.exists(upload_folder)}")
        
        file_path = os.path.join(upload_folder, unique_filename)
        print(f"Target file path: {file_path}")
        
        try:
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            print(f"File saved successfully. Size: {file_size} bytes ({file_size/1024:.2f} KB)")
            print(f"File exists after save: {os.path.exists(file_path)}")
        except Exception as e:
            print(f"ERROR saving file: {str(e)}")
            return jsonify({'error': f'Failed to save file: {str(e)}'}), 500
        
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
        
        # Return the URL path and media information
        response_data = {
            'url': f'/uploads/{unique_filename}',
            'filename': unique_filename,
            'type': media_type,
            'category': media_category,
            'size': file_size,
            'size_kb': f"{file_size/1024:.2f} KB"
        }
        print(f"Response data: {response_data}")
        print("=== MEDIA UPLOAD COMPLETED SUCCESSFULLY ===")
        return jsonify(response_data)
    
    print(f"ERROR: File type not allowed for {file.filename}")
    return jsonify({'error': 'File type not allowed'}), 400
