from app import app, db, Timeline, TimelineMember, User

# This script checks existing community timelines and their members
# It's a one-time-use script that can be deleted after verification

with app.app_context():
    # Get all community timelines
    community_timelines = Timeline.query.filter_by(timeline_type='community').all()
    
    print(f"Found {len(community_timelines)} community timelines:")
    
    for timeline in community_timelines:
        print(f"\nTimeline ID: {timeline.id}")
        print(f"Name: {timeline.name}")
        print(f"Created by user ID: {timeline.created_by}")
        
        # Get creator's username
        creator = User.query.get(timeline.created_by)
        creator_name = creator.username if creator else "Unknown"
        print(f"Creator: {creator_name}")
        
        # Get members
        members = TimelineMember.query.filter_by(timeline_id=timeline.id).all()
        print(f"Members count: {len(members)}")
        
        if members:
            print("Members:")
            for member in members:
                user = User.query.get(member.user_id)
                username = user.username if user else f"Unknown (ID: {member.user_id})"
                print(f"  - {username} (ID: {member.user_id}, Role: {member.role})")
