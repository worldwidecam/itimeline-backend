import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url
import os
from dotenv import load_dotenv

# Load environment variables if available
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME', 'dnjwvuxn7'),
    api_key=os.getenv('CLOUDINARY_API_KEY', '926174651153599'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET', '6xeVWAXdvJufhHHqUw0HQz2Vvdk'),
    secure=True
)

def upload_file(file, folder="timeline_forum", **options):
    """
    Upload a file to Cloudinary with optional transformations
    
    Args:
        file: File object to upload (can be a file-like object or a path)
        folder: Folder name in Cloudinary to store the file
        options: Additional options for upload (transformations, etc.)
        
    Returns:
        Dictionary containing upload result including public_id and secure_url
    """
    try:
        # Set default options for optimization
        default_options = {
            'folder': folder,
            'resource_type': "auto",  # Automatically detect resource type (image, video, etc.)
        }
        
        # Check if the file has a content_type attribute
        has_content_type = hasattr(file, 'content_type') and file.content_type
        
        # Check if the file is an image
        is_image = False
        if has_content_type and file.content_type.startswith('image/'):
            is_image = True
        elif hasattr(file, 'filename') and file.filename:
            # Try to determine content type from filename
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file.filename)
            is_image = mime_type and mime_type.startswith('image/')
        
        # For images, add auto-optimization by default
        if is_image:
            default_options.update({
                'quality': 'auto',  # Auto-select optimal quality
                'fetch_format': 'auto',  # Auto-select optimal format
            })
        
        # Check if the file is an audio file
        is_audio = False
        if has_content_type and file.content_type.startswith('audio/'):
            is_audio = True
        elif hasattr(file, 'filename') and file.filename:
            # Try to determine content type from filename
            import mimetypes
            mime_type, _ = mimetypes.guess_type(file.filename)
            is_audio = mime_type and mime_type.startswith('audio/')
        
        # For audio files, add specific optimizations
        if is_audio:
            default_options.update({
                'resource_type': 'auto',  # Let Cloudinary automatically detect the resource type
                'use_filename': True,     # Use the original filename
                'unique_filename': True,  # Ensure the filename is unique
                'folder': 'timeline_forum/music'  # Use the same folder as the profile music uploader
            })
            
        # Merge default options with provided options
        upload_options = {**default_options, **options}
        
        # Print debug info
        print(f"Uploading file to Cloudinary: {file.filename if hasattr(file, 'filename') else file.name}")
        print(f"Content type: {file.content_type if hasattr(file, 'content_type') else 'unknown'}")
        
        # Check if we need to handle a file without filename attribute
        if not hasattr(file, 'filename') and hasattr(file, 'name'):
            # For standard file objects that have 'name' but not 'filename'
            print(f"Using file.name as filename: {file.name}")
            
            # Create a temporary file with the correct attributes
            from werkzeug.datastructures import FileStorage
            import os
            
            # Get the original file content
            original_position = file.tell()
            file.seek(0)
            content = file.read()
            file.seek(original_position)  # Reset position
            
            # Create a FileStorage object
            temp_file = FileStorage(
                stream=file,
                filename=os.path.basename(file.name) if hasattr(file, 'name') else 'uploaded_file',
                content_type=None
            )
            file = temp_file
        
        # Upload the file to Cloudinary
        print(f"Uploading file to Cloudinary with options: {upload_options}")
        result = cloudinary.uploader.upload(file, **upload_options)
        
        print(f"Upload successful: {result['secure_url']}")
        
        return {
            'success': True,
            'public_id': result['public_id'],
            'url': result['secure_url'],
            'resource_type': result['resource_type']
        }
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_optimized_url(public_id, **options):
    """
    Generate an optimized URL for a Cloudinary resource
    
    Args:
        public_id: The public ID of the resource
        options: Transformation options
        
    Returns:
        Optimized URL string
    """
    # Default optimization options
    default_options = {
        'fetch_format': 'auto',
        'quality': 'auto'
    }
    
    # Merge default options with provided options
    url_options = {**default_options, **options}
    
    # Generate the URL
    url, _ = cloudinary_url(public_id, **url_options)
    return url

def get_transformed_url(public_id, width=None, height=None, crop=None, **options):
    """
    Generate a transformed URL for a Cloudinary resource
    
    Args:
        public_id: The public ID of the resource
        width: Desired width
        height: Desired height
        crop: Crop mode (fill, crop, scale, etc.)
        options: Additional transformation options
        
    Returns:
        Transformed URL string
    """
    # Set up transformation options
    transform_options = {
        'fetch_format': 'auto',
        'quality': 'auto'
    }
    
    # Add dimensions if provided
    if width:
        transform_options['width'] = width
    if height:
        transform_options['height'] = height
    if crop:
        transform_options['crop'] = crop
        # If using crop mode and no gravity specified, use auto
        if crop in ['crop', 'fill'] and 'gravity' not in options:
            transform_options['gravity'] = 'auto'
    
    # Merge with additional options
    transform_options.update(options)
    
    # Generate the URL
    url, _ = cloudinary_url(public_id, **transform_options)
    return url

def delete_file(public_id):
    """
    Delete a file from Cloudinary
    
    Args:
        public_id: The public ID of the file to delete
        
    Returns:
        Dictionary containing the result of the deletion operation
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        return {
            'success': True,
            'result': result
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
