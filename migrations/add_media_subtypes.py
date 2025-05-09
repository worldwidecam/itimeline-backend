from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os
import sys

# Add the parent directory to the path so we can import from the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create a minimal Flask app for the migration
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timeline_forum.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def run_migration():
    """
    Add media_subtype and cloudinary_id columns to the Event table
    """
    print("Starting migration to add media_subtype and cloudinary_id columns to the Event table...")
    
    with app.app_context():
        # Check if the columns already exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('event')]
        
        # Add media_subtype column if it doesn't exist
        if 'media_subtype' not in columns:
            print("Adding media_subtype column...")
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE event ADD COLUMN media_subtype VARCHAR(50)'))
                conn.commit()
            print("media_subtype column added successfully.")
        else:
            print("media_subtype column already exists, skipping.")
        
        # Add cloudinary_id column if it doesn't exist
        if 'cloudinary_id' not in columns:
            print("Adding cloudinary_id column...")
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE event ADD COLUMN cloudinary_id VARCHAR(255)'))
                conn.commit()
            print("cloudinary_id column added successfully.")
        else:
            print("cloudinary_id column already exists, skipping.")
        
        # Update existing media events with appropriate subtypes based on media_type or file extension
        print("Updating existing media events with appropriate subtypes...")
        
        # Get all media events
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT id, media_url, media_type FROM event WHERE type = 'media'"))
            media_events = result.fetchall()
        
        for event in media_events:
            event_id = event[0]
            media_url = event[1]
            media_type = event[2]
            
            # Determine media subtype
            media_subtype = None
            
            if media_url:
                # Check media_type first
                if media_type:
                    if 'image' in media_type:
                        media_subtype = 'media_image'
                    elif 'video' in media_type:
                        media_subtype = 'media_video'
                    elif 'audio' in media_type:
                        media_subtype = 'media_audio'
                
                # If media_subtype is still None, try to determine from URL
                if media_subtype is None:
                    # Extract file extension from URL
                    file_ext = media_url.split('.')[-1].lower() if '.' in media_url else None
                    
                    if file_ext:
                        if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']:
                            media_subtype = 'media_image'
                        elif file_ext in ['mp4', 'webm', 'ogg', 'mov']:
                            media_subtype = 'media_video'
                        elif file_ext in ['mp3', 'wav', 'ogg', 'aac']:
                            media_subtype = 'media_audio'
            
            # If we determined a subtype, update the event
            if media_subtype:
                with db.engine.connect() as conn:
                    conn.execute(text(f"UPDATE event SET media_subtype = '{media_subtype}' WHERE id = {event_id}"))
                    conn.commit()
                print(f"Updated event {event_id} with media_subtype: {media_subtype}")
        
        # Extract cloudinary_id from media_url for existing events
        print("Extracting cloudinary_id from media_url for existing events...")
        
        for event in media_events:
            event_id = event[0]
            media_url = event[1]
            
            if media_url and ('cloudinary.com' in media_url or 'res.cloudinary' in media_url):
                # Try to extract public_id from URL
                # Example: https://res.cloudinary.com/dnjwvuxn7/image/upload/v1620123456/timeline_forum/abcdef123456
                parts = media_url.split('/')
                public_id = None
                
                if 'upload' in parts:
                    upload_index = parts.index('upload')
                    if upload_index + 2 < len(parts):  # Make sure we have enough parts
                        # Skip the version part (v1234567890)
                        if parts[upload_index + 1].startswith('v'):
                            public_id = '/'.join(parts[upload_index + 2:])
                        else:
                            public_id = '/'.join(parts[upload_index + 1:])
                
                if public_id:
                    with db.engine.connect() as conn:
                        conn.execute(text(f"UPDATE event SET cloudinary_id = '{public_id}' WHERE id = {event_id}"))
                        conn.commit()
                    print(f"Updated event {event_id} with cloudinary_id: {public_id}")
        
        print("Migration completed successfully!")

if __name__ == '__main__':
    run_migration()
