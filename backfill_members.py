from app import app, db, Timeline, TimelineMember, User
from datetime import datetime

# This script backfills member data for existing community timelines
# It's a one-time-use script that can be deleted after running

with app.app_context():
    # Get all community timelines
    community_timelines = Timeline.query.filter_by(timeline_type='community').all()
    
    print(f"Found {len(community_timelines)} community timelines to process")
    
    for timeline in community_timelines:
        # Check if creator is already a member
        creator_member = TimelineMember.query.filter_by(
            timeline_id=timeline.id,
            user_id=timeline.created_by
        ).first()
        
        if not creator_member:
            # Add creator as Admin
            creator = User.query.get(timeline.created_by)
            creator_name = creator.username if creator else f"User {timeline.created_by}"
            
            new_member = TimelineMember(
                timeline_id=timeline.id,
                user_id=timeline.created_by,
                role='Admin',  # Timeline creators get Admin role
                joined_at=timeline.created_at or datetime.now()
            )
            
            db.session.add(new_member)
            print(f"Added creator {creator_name} (ID: {timeline.created_by}) as Admin to timeline {timeline.name} (ID: {timeline.id})")
        
        # Always ensure Brahdyssey (user ID 1) is a member with SiteOwner role
        # (only if not already the creator)
        if timeline.created_by != 1:
            brahdyssey_member = TimelineMember.query.filter_by(
                timeline_id=timeline.id,
                user_id=1
            ).first()
            
            if not brahdyssey_member:
                brahdyssey = User.query.get(1)
                brahdyssey_name = brahdyssey.username if brahdyssey else "Brahdyssey"
                
                new_brahdyssey = TimelineMember(
                    timeline_id=timeline.id,
                    user_id=1,
                    role='SiteOwner',
                    joined_at=datetime.now()
                )
                
                db.session.add(new_brahdyssey)
                print(f"Added {brahdyssey_name} as SiteOwner to timeline {timeline.name} (ID: {timeline.id})")
    
    # Commit all changes
    db.session.commit()
    print("Backfill complete!")
    
    # Verify the results
    print("\nVerifying results:")
    for timeline in community_timelines:
        members = TimelineMember.query.filter_by(timeline_id=timeline.id).all()
        print(f"Timeline {timeline.name} (ID: {timeline.id}) now has {len(members)} members:")
