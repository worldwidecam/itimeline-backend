import os
import json
from flask import Blueprint, jsonify, current_app
import cloudinary
import cloudinary.api
from datetime import datetime

media_bp = Blueprint('media', __name__)

@media_bp.route('/api/media-files', methods=['GET'])
def get_media_files():
    """
    Retrieve a list of media files from both Cloudinary and local storage
    """
    print("\n===== FETCHING MEDIA FILES =====")
    
    media_files = []
    
    # First, try to get files from Cloudinary
    try:
        print("Fetching files from Cloudinary...")
        
        # Get files from the timeline_media folder in Cloudinary
        result = cloudinary.api.resources(
            type="upload",
            prefix="timeline_media/",
            max_results=100,
            resource_type="auto"
        )
        
        if 'resources' in result:
            print(f"Found {len(result['resources'])} files in Cloudinary")
            
            for resource in result['resources']:
                # Extract the file information
                url = resource['secure_url']
                public_id = resource['public_id']
                resource_type = resource['resource_type']
                format = resource['format']
                
                # Determine media type based on resource_type and format
                media_type = resource_type
                if resource_type == 'image':
                    media_type = 'image'
                elif resource_type == 'video':
                    media_type = 'video'
                elif resource_type == 'raw' and format in ['mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a']:
                    media_type = 'audio'
                
                # Get the filename from the public_id
                filename = public_id.split('/')[-1]
                if format:
                    filename = f"{filename}.{format}"
                
                # Get the creation time
                created_at = datetime.fromtimestamp(resource['created_at']).isoformat()
                
                # Add to the list
                media_files.append({
                    'id': public_id,
                    'name': filename,
                    'url': url,
                    'type': media_type,
                    'size': resource.get('bytes', 0),
                    'uploadedAt': created_at,
                    'cloudinaryId': public_id,
                    'storage': 'cloudinary'
                })
        
    except Exception as e:
        print(f"Error fetching files from Cloudinary: {str(e)}")
    
    # Then, get files from local storage
    try:
        print("Fetching files from local storage...")
        
        # Get the uploads directory
        uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads')
        
        if os.path.exists(uploads_dir):
            # List all files in the directory
            for filename in os.listdir(uploads_dir):
                file_path = os.path.join(uploads_dir, filename)
                
                # Skip directories
                if not os.path.isfile(file_path):
                    continue
                
                # Get file information
                size = os.path.getsize(file_path)
                modified_time = os.path.getmtime(file_path)
                
                # Determine media type based on file extension
                ext = filename.split('.')[-1].lower() if '.' in filename else ''
                media_type = 'other'
                
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']:
                    media_type = 'image'
                elif ext in ['mp4', 'webm', 'ogg', 'mov', 'avi', 'wmv', 'flv', 'mkv']:
                    media_type = 'video'
                elif ext in ['mp3', 'wav', 'ogg', 'aac', 'flac', 'm4a']:
                    media_type = 'audio'
                
                # Add to the list
                media_files.append({
                    'id': f"local_{filename}",
                    'name': filename,
                    'url': f"/static/uploads/{filename}",
                    'type': media_type,
                    'size': size,
                    'uploadedAt': datetime.fromtimestamp(modified_time).isoformat(),
                    'storage': 'local'
                })
            
            print(f"Found {len(media_files)} files in local storage")
        else:
            print(f"Uploads directory not found: {uploads_dir}")
    
    except Exception as e:
        print(f"Error fetching files from local storage: {str(e)}")
    
    # Sort by upload time (newest first)
    media_files.sort(key=lambda x: x['uploadedAt'], reverse=True)
    
    print(f"Total media files found: {len(media_files)}")
    print("===== MEDIA FILES FETCH COMPLETE =====\n")
    
    return jsonify(media_files)
