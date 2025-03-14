"""
Add original timeline tags to events.

This script modifies the get_timeline_v3_events function to include
the original timeline's tag when an event is viewed from a different timeline.
"""

from app import app, db, Timeline, Event, Tag
from flask import Flask, jsonify
import sys

def modify_get_timeline_events():
    """
    Update the get_timeline_v3_events function to include original timeline tags.
    
    This modification ensures that when an event is viewed from a timeline other than
    its original timeline, the original timeline's tag is included in the event's tags.
    """
    
    # The original function is in app.py and we can't modify it directly from this script
    # Instead, we'll create a utility function that can be called from app.py
    
    def add_original_timeline_tag(event_dict, timeline_id):
        """
        Add the original timeline's tag to an event if it's being viewed from another timeline.
        
        Args:
            event_dict: The event dictionary to modify
            timeline_id: The ID of the timeline being viewed
            
        Returns:
            The modified event dictionary
        """
        with app.app_context():
            # Get the original timeline
            original_timeline = Timeline.query.get(event_dict['timeline_id'])
            current_timeline = Timeline.query.get(timeline_id)
            
            # If the event is being viewed from a different timeline than its original
            if original_timeline and original_timeline.id != int(timeline_id):
                # Find or create a tag for the original timeline
                original_tag_name = original_timeline.name.lower()
                original_tag = Tag.query.filter(db.func.lower(Tag.name) == original_tag_name).first()
                
                if not original_tag:
                    original_tag = Tag(
                        name=original_tag_name,
                        timeline_id=original_timeline.id
                    )
                    db.session.add(original_tag)
                    db.session.commit()
                
                # Check if this tag is already in the event's tags
                tag_exists = False
                for tag in event_dict['tags']:
                    if tag['name'].lower() == original_tag_name:
                        tag_exists = True
                        break
                
                # Add the original timeline's tag if it's not already there
                if not tag_exists:
                    event_dict['tags'].append({
                        'id': original_tag.id,
                        'name': original_tag.name,
                        'is_original_timeline': True  # Flag to identify this as the original timeline
                    })
            
            return event_dict
    
    # Export the function so it can be imported in app.py
    return add_original_timeline_tag

if __name__ == "__main__":
    print("This script provides a utility function for app.py.")
    print("To use it, import the function in app.py and call it when processing events.")
    sys.exit(0)
