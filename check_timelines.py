"""
Check the current state of timelines and tags in the database.
"""

from app import app, db, Timeline, Event, Tag
from flask import Flask
import sys

def check_database():
    with app.app_context():
        print("Checking database state after fixes...")
        
        # Check timelines
        timelines = Timeline.query.order_by(Timeline.name).all()
        print(f"\nTimelines ({len(timelines)}):")
        for timeline in timelines:
            print(f"  ID: {timeline.id}, Name: '{timeline.name}'")
            
            # Count events directly in this timeline
            direct_events = Event.query.filter_by(timeline_id=timeline.id).count()
            
            # Count events that reference this timeline
            referenced_events = timeline.referenced_events.count()
            
            print(f"    Direct events: {direct_events}, Referenced events: {referenced_events}")
        
        # Check for any remaining timelines with '#' prefix
        hashtag_timelines = Timeline.query.filter(Timeline.name.startswith('#')).all()
        if hashtag_timelines:
            print(f"\nWARNING: Found {len(hashtag_timelines)} timelines still with '#' prefix:")
            for timeline in hashtag_timelines:
                print(f"  ID: {timeline.id}, Name: '{timeline.name}'")
        else:
            print("\nNo timelines with '#' prefix found. Fix was successful!")
        
        # Check tags
        tags = Tag.query.order_by(Tag.name).all()
        print(f"\nTags ({len(tags)}):")
        for tag in tags:
            timeline_name = "None"
            if tag.timeline_id:
                timeline = Timeline.query.get(tag.timeline_id)
                if timeline:
                    timeline_name = timeline.name
            
            print(f"  ID: {tag.id}, Name: '{tag.name}', Timeline: '{timeline_name}'")
            
            # Count events with this tag
            event_count = tag.events.count()
            print(f"    Used in {event_count} events")

if __name__ == "__main__":
    check_database()
