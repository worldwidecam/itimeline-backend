from flask import Blueprint, jsonify, current_app
import cloudinary
import cloudinary.api
import os

cloudinary_bp = Blueprint('cloudinary', __name__)

# Note: blueprint is registered with url_prefix='/api' in app.py, so do NOT include '/api' here
@cloudinary_bp.route('/cloudinary/audio-files', methods=['GET'])
def get_audio_files():
    """
    Get a list of audio files from the Cloudinary timeline_forum/music folder
    """
    try:
        # Get files from the timeline_forum/music folder
        result = cloudinary.api.resources(
            type="upload",
            prefix="timeline_forum/music",
            resource_type="video",  # Cloudinary uses 'video' resource type for audio files
            max_results=100
        )
        
        # Format the response
        files = []
        for resource in result.get('resources', []):
            # Extract useful information about each file
            file_info = {
                'public_id': resource['public_id'],
                'url': resource['secure_url'],
                'format': resource.get('format', ''),
                'resource_type': resource['resource_type'],
                'created_at': resource['created_at'],
                'bytes': resource['bytes'],
                'type': resource['type'],
                # Extract filename from public_id
                'filename': os.path.basename(resource['public_id'])
            }
            files.append(file_info)
        
        # Sort by creation date (newest first)
        files.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({
            'success': True,
            'files': files,
            'total': len(files)
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching Cloudinary audio files: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
