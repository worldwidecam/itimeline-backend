"""
Fix existing timelines with '#' prefix.

This script:
1. Finds all timelines with names starting with '#'
2. Creates new timelines with the same name but without the '#' prefix
3. Migrates all events from the old timelines to the new ones
4. Updates tag associations
5. Deletes the old timelines

Run this script once to fix existing data after updating the hashtag system.
"""

from app import app, db, Timeline, Event, Tag
from flask import Flask
import sys

def fix_hashtag_timelines():
    with app.app_context():
        print("Starting hashtag timeline fix script...")
        
        # Find all timelines with names starting with '#'
        hashtag_timelines = Timeline.query.filter(Timeline.name.startswith('#')).all()
        print(f"Found {len(hashtag_timelines)} timelines with '#' prefix")
        
        for old_timeline in hashtag_timelines:
            # Get the name without the '#' prefix
            clean_name = old_timeline.name[1:]
            capitalized_name = clean_name.upper()
            
            print(f"Processing timeline: {old_timeline.name} -> {capitalized_name}")
            
            # Check if a timeline with the clean name already exists
            existing_timeline = Timeline.query.filter(
                db.func.lower(Timeline.name) == db.func.lower(clean_name)
            ).first()
            
            if existing_timeline:
                print(f"  Timeline '{capitalized_name}' already exists (ID: {existing_timeline.id})")
                new_timeline = existing_timeline
            else:
                # Create a new timeline with the clean name
                new_timeline = Timeline(
                    name=capitalized_name,
                    description=f"Timeline for #{capitalized_name}",
                    created_by=old_timeline.created_by,
                    created_at=old_timeline.created_at
                )
                db.session.add(new_timeline)
                db.session.flush()  # Get the new timeline ID
                print(f"  Created new timeline '{capitalized_name}' (ID: {new_timeline.id})")
            
            # Find all events directly in the old timeline
            direct_events = Event.query.filter_by(timeline_id=old_timeline.id).all()
            print(f"  Found {len(direct_events)} direct events to migrate")
            
            # Migrate direct events to the new timeline
            for event in direct_events:
                event.timeline_id = new_timeline.id
                print(f"    Migrated event {event.id}: {event.title}")
            
            # Find all events that reference the old timeline
            referenced_events = old_timeline.referenced_events.all()
            print(f"  Found {len(referenced_events)} referenced events to update")
            
            # Update event references
            for event in referenced_events:
                # Remove reference to old timeline
                event.referenced_in.remove(old_timeline)
                # Add reference to new timeline if not already there
                if new_timeline not in event.referenced_in:
                    event.referenced_in.append(new_timeline)
                print(f"    Updated references for event {event.id}: {event.title}")
            
            # Find tags associated with the old timeline
            associated_tags = Tag.query.filter_by(timeline_id=old_timeline.id).all()
            print(f"  Found {len(associated_tags)} tags to update")
            
            # Update tag associations
            for tag in associated_tags:
                tag.timeline_id = new_timeline.id
                print(f"    Updated tag {tag.id}: {tag.name}")
            
            # Mark the old timeline for deletion
            db.session.delete(old_timeline)
            print(f"  Marked timeline '{old_timeline.name}' for deletion")
        
        # Commit all changes
        try:
            db.session.commit()
            print("All changes committed successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing changes: {str(e)}")
            return False
        
        return True

if __name__ == "__main__":
    success = fix_hashtag_timelines()
    sys.exit(0 if success else 1)
