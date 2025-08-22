"""
Community Timeline API Routes

This module contains all routes related to community timelines, including:
- Creating and managing community timelines
- Managing timeline members and roles
- Handling access requests for private timelines
- Sharing posts between communities
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError
import sqlite3

# Create blueprint first, before any circular imports can happen
community_bp = Blueprint('community', __name__)

# Import schemas only - models will be imported inside route functions
from api_docs import (
    TimelineSchema, TimelineMemberSchema, TimelineMemberCreateSchema,
    EventTimelineAssociationSchema, EventSchema
)

# Schemas
timeline_schema = TimelineSchema()
timelines_schema = TimelineSchema(many=True)
member_schema = TimelineMemberSchema()
members_schema = TimelineMemberSchema(many=True)
member_create_schema = TimelineMemberCreateSchema()
association_schema = EventTimelineAssociationSchema()
associations_schema = EventTimelineAssociationSchema(many=True)
event_schema = EventSchema()

# Helper functions
def get_user_id():
    """Get the current user's ID from the JWT token"""
    return get_jwt_identity()

def check_timeline_access(timeline_id, required_role=None):
    """
    Check if the current user has access to the timeline
    
    Args:
        timeline_id: ID of the timeline to check
        required_role: Minimum role required (None = any member, 'moderator', 'admin')
        
    Returns:
        tuple: (timeline, membership, has_access)
    """
    user_id = get_user_id()
    
    try:
        # Get timeline information using SQLAlchemy
        timeline = Timeline.query.get(timeline_id)
        if not timeline:
            return None, None, False
        
        # SiteOwner (user ID 1) always has access to any timeline
        if user_id == 1:
            membership = TimelineMember.query.filter_by(
                timeline_id=timeline_id, user_id=user_id
            ).first()
            return timeline, membership, True
        
        # Check if user is an active member of the timeline
        membership = TimelineMember.query.filter_by(
            timeline_id=timeline_id, 
            user_id=user_id,
            is_active_member=True
        ).first()
        
        # If not a member, no access
        if not membership:
            return timeline, None, False
        
        # Check if user has the required role
        if required_role:
            role_hierarchy = {'member': 1, 'moderator': 2, 'admin': 3, 'SiteOwner': 4}
            user_role_level = role_hierarchy.get(membership.role, 0)
            required_role_level = role_hierarchy.get(required_role, 0)
            has_access = user_role_level >= required_role_level
        else:
            has_access = True
        
        return timeline, membership, has_access
        
    except Exception as e:
        logger.error(f"Error checking timeline access: {str(e)}")
        raise e

# Routes
@community_bp.route('/timelines/community', methods=['POST'])
@jwt_required()
def create_community_timeline():
    """Create a new community timeline"""
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Set timeline type to community
        data['timeline_type'] = 'community'
        
        # Create timeline
        new_timeline = Timeline(
            name=data.get('name'),
            description=data.get('description', ''),
            timeline_type='community',
            visibility=data.get('visibility', 'public'),
            created_by=get_user_id(),
            created_at=datetime.now()
        )
        
        # Add to database
        db.session.add(new_timeline)
        db.session.flush()  # Get the timeline ID
        
        # Add creator as admin
        admin = TimelineMember(
            timeline_id=new_timeline.id,
            user_id=get_user_id(),
            role='admin',
            joined_at=datetime.now()
        )
        db.session.add(admin)
        
        # Commit changes
        db.session.commit()
        
        # Return the new timeline
        result = timeline_schema.dump(new_timeline)
        return jsonify(result), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Timeline name already exists"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@community_bp.route('/timelines/<int:timeline_id>/members', methods=['GET'])
@jwt_required()
def get_timeline_members(timeline_id):
    """Get all active members of a timeline using SQLAlchemy"""
    # Remove access control - allow anyone to view member lists
    user_id = get_user_id()
    
    try:
        # Get timeline for later use
        timeline = Timeline.query.get_or_404(timeline_id)
        
        # Get all active members with user information using SQLAlchemy
        members = db.session.query(
            TimelineMember, User
        ).join(
            User, TimelineMember.user_id == User.id
        ).filter(
            TimelineMember.timeline_id == timeline_id,
            TimelineMember.is_active_member == True  # Only get active members
        ).order_by(
            TimelineMember.joined_at.asc()
        ).all()
        
        result = []
        
        for member, user in members:
            member_data = {
                'id': member.id,
                'timeline_id': member.timeline_id,
                'user_id': member.user_id,
                'role': member.role,
                'is_active_member': bool(member.is_active_member),
                'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                'invited_by': member.invited_by,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'avatar_url': user.avatar_url,
                    'bio': user.bio
                }
            }
            result.append(member_data)
        
        # Check if Brahdyssey (user ID 1) is already in the members list
        brahdyssey_in_members = any(m['user_id'] == 1 for m in result)
        
        # If Brahdyssey is not in the members list, add them with SiteOwner role
        if not brahdyssey_in_members:
            brahdyssey_user = User.query.get(1)
            if brahdyssey_user:
                brahdyssey_data = {
                    'id': None,  # Virtual member, no database ID
                    'timeline_id': timeline_id,
                    'user_id': 1,
                    'role': 'SiteOwner',
                    'is_active_member': True,
                    'joined_at': timeline.created_at.isoformat() if timeline.created_at else None,
                    'invited_by': None,
                    'user': {
                        'id': 1,
                        'username': brahdyssey_user.username,
                        'email': brahdyssey_user.email,
                        'avatar_url': brahdyssey_user.avatar_url,
                        'bio': brahdyssey_user.bio
                    }
                }
                result.append(brahdyssey_data)
        
        # Check if the creator is already in the members list
        creator_in_members = any(m['user_id'] == timeline.created_by for m in result)
        
        # If the creator is not in the members list and is not Brahdyssey, add them with Admin role
        if not creator_in_members and timeline.created_by != 1:
            creator_user = User.query.get(timeline.created_by)
            if creator_user:
                creator_data = {
                    'id': None,  # Virtual member, no database ID
                    'timeline_id': timeline_id,
                    'user_id': timeline.created_by,
                    'role': 'admin',
                    'is_active_member': True,
                    'joined_at': timeline.created_at.isoformat() if timeline.created_at else None,
                    'invited_by': None,
                    'user': {
                        'id': timeline.created_by,
                        'username': creator_user.username,
                        'email': creator_user.email,
                        'avatar_url': creator_user.avatar_url,
                        'bio': creator_user.bio
                    }
                }
                result.append(creator_data)
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error getting timeline members: {str(e)}")
        return jsonify({"error": str(e)}), 500

@community_bp.route('/timelines/<int:timeline_id>/members', methods=['POST'])
@jwt_required()
def add_timeline_member(timeline_id):
    """Add a new member to a timeline"""
    timeline, membership, has_access = check_timeline_access(timeline_id, 'moderator')
    
    if not has_access:
        return jsonify({"error": "Access denied"}), 403
    
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Validate data
        validated_data = member_create_schema.load(data)
        
        # Check if user exists
        user = User.query.get(validated_data['user_id'])
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Check if user is already a member
        existing = TimelineMember.query.filter_by(
            timeline_id=timeline_id, user_id=validated_data['user_id']
        ).first()
        
        if existing:
            return jsonify({"error": "User is already a member"}), 400
        
        # Only admins can add other admins
        if validated_data.get('role') == 'admin' and membership.role != 'admin':
            return jsonify({"error": "Only admins can add other admins"}), 403
        
        # Add member
        new_member = TimelineMember(
            timeline_id=timeline_id,
            user_id=validated_data['user_id'],
            role=validated_data.get('role', 'member'),
            joined_at=datetime.now(),
            invited_by=get_user_id()
        )
        
        db.session.add(new_member)
        db.session.commit()
        
        result = member_schema.dump(new_member)
        return jsonify(result), 201
        
    except ValidationError as err:
        return jsonify({"error": err.messages}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>', methods=['DELETE'])
@jwt_required()
def remove_timeline_member(timeline_id, user_id):
    """Remove a member from a timeline by setting is_active_member to false"""
    current_user_id = get_user_id()
    timeline, membership, has_access = check_timeline_access(timeline_id, 'moderator')
    
    if not has_access:
        return jsonify({"error": "Access denied. You need moderator privileges to remove members."}), 403
    
    # Get the member to remove
    member = TimelineMember.query.filter_by(
        timeline_id=timeline_id, user_id=user_id
    ).first_or_404()
    
    # Hierarchical permission checks
    
    # 1. Prevent removing the SiteOwner (user ID 1) by anyone
    if user_id == 1 or member.role == 'SiteOwner':
        return jsonify({"error": "Cannot remove the site owner from any timeline"}), 403
    
    # 2. Only admins can remove admins
    if member.role == 'admin' and membership.role != 'admin':
        return jsonify({"error": "Only admins can remove admins"}), 403
    
    # 3. Prevent removing the last admin
    if member.role == 'admin':
        admin_count = TimelineMember.query.filter_by(
            timeline_id=timeline_id, role='admin'
        ).count()
        
        if admin_count <= 1:
            return jsonify({"error": "Cannot remove the last admin"}), 400
    
    # 4. Moderators can only remove regular members, not other moderators
    if member.role == 'moderator' and membership.role == 'moderator':
        return jsonify({"error": "Moderators cannot remove other moderators"}), 403
    
    # 5. Users cannot remove themselves (should use leave timeline endpoint instead)
    if user_id == current_user_id:
        return jsonify({"error": "Cannot remove yourself. Use the leave timeline feature instead."}), 400
    
    # Set member as inactive instead of deleting
    member.is_active_member = False
    
    # Record the action in the database for audit purposes
    try:
        # Add a timeline action to track who removed the member
        action = TimelineAction(
            timeline_id=timeline_id,
            user_id=current_user_id,
            action_type='member_removed',
            target_user_id=user_id,
            details=f"User {user_id} removed from timeline by user {current_user_id}",
            created_at=datetime.now()
        )
        db.session.add(action)
        db.session.commit()
        
        return jsonify({
            "message": "Member removed successfully",
            "removed_user_id": user_id,
            "removed_by": current_user_id
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Error removing member: {str(e)}"}), 500

@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>/role', methods=['PUT'])
@jwt_required()
def update_member_role(timeline_id, user_id):
    """Update a member's role in a timeline"""
    timeline, membership, has_access = check_timeline_access(timeline_id, 'admin')
    
    if not has_access:
        return jsonify({"error": "Access denied"}), 403
    
    # Parse request data
    data = request.get_json()
    if not data or 'role' not in data:
        return jsonify({"error": "Role not provided"}), 400
    
    new_role = data['role']
    # Include SiteOwner as a valid role, but with restrictions
    if new_role not in ['SiteOwner', 'admin', 'moderator', 'member']:
        return jsonify({"error": "Invalid role"}), 400
        
    # Only user ID 1 can be assigned the SiteOwner role
    if new_role == 'SiteOwner' and user_id != 1:
        return jsonify({"error": "Only the site owner (user ID 1) can have the SiteOwner role"}), 403
        
    # Prevent changing the role of user ID 1 (SiteOwner)
    current_user_id = get_user_id()
    if user_id == 1 and current_user_id != 1:
        return jsonify({"error": "Cannot change the role of the site owner"}), 403
    
    # Get the member to update
    member = TimelineMember.query.filter_by(
        timeline_id=timeline_id, user_id=user_id
    ).first_or_404()
    
    # Prevent downgrading SiteOwner role
    if member.role == 'SiteOwner' and new_role != 'SiteOwner' and user_id == 1:
        return jsonify({"error": "Cannot downgrade the site owner's role"}), 403
    
    # Update role
    member.role = new_role
    db.session.commit()
    
    result = member_schema.dump(member)
    return jsonify(result), 200

@community_bp.route('/timelines/<int:timeline_id>/visibility', methods=['PUT'])
@jwt_required()
def update_timeline_visibility(timeline_id):
    """Update a timeline's visibility (public/private)"""
    timeline, membership, has_access = check_timeline_access(timeline_id, 'admin')
    
    if not has_access:
        return jsonify({"error": "Access denied"}), 403
    
    # Parse request data
    data = request.get_json()
    if not data or 'visibility' not in data:
        return jsonify({"error": "Visibility not provided"}), 400
    
    new_visibility = data['visibility']
    if new_visibility not in ['public', 'private']:
        return jsonify({"error": "Invalid visibility"}), 400
    
    # Check if visibility is changing
    if timeline.visibility == new_visibility:
        return jsonify({"message": "Visibility unchanged"}), 200
    
    # Check cooldown period if changing to private
    if new_visibility == 'private' and timeline.privacy_changed_at:
        cooldown_days = 10
        cooldown_end = timeline.privacy_changed_at + timedelta(days=cooldown_days)
        
        if datetime.now() < cooldown_end:
            days_left = (cooldown_end - datetime.now()).days + 1
            return jsonify({
                "error": f"Cannot change visibility yet. Please wait {days_left} more days."
            }), 400
    
    # Update visibility
    timeline.visibility = new_visibility
    timeline.privacy_changed_at = datetime.now()
    db.session.commit()
    
    result = timeline_schema.dump(timeline)
    return jsonify(result), 200

@community_bp.route('/timelines/<int:timeline_id>/access-requests', methods=['POST'])
@jwt_required()
def request_timeline_access(timeline_id):
    """Request access to a timeline - handles both public and private timelines"""
    user_id = get_user_id()
    print(f"DEBUG: User {user_id} requesting access to timeline {timeline_id}")
    timeline = Timeline.query.get_or_404(timeline_id)
    
    # Check if user is already a member
    existing = TimelineMember.query.filter_by(
        timeline_id=timeline_id, user_id=user_id
    ).first()
    
    if existing:
        if existing.is_active_member:
            print(f"DEBUG: User {user_id} is already an active member of timeline {timeline_id}")
            return jsonify({"message": "You are already a member of this timeline", "status": "already_member"}), 200
        else:
            print(f"DEBUG: User {user_id} already has a pending request for timeline {timeline_id}")
            return jsonify({"message": "Your request to join this timeline is pending approval", "status": "pending"}), 200
    
    # For public timelines, auto-accept the user as a member
    # For private timelines, create a pending request
    is_public = timeline.visibility != 'private'
    role = 'member' if is_public else 'pending'
    
    # Create the membership record
    new_member = TimelineMember(
        timeline_id=timeline_id,
        user_id=user_id,
        role=role,
        is_active_member=is_public,  # True for public, False for private
        joined_at=datetime.now()
    )
    
    db.session.add(new_member)
    
    try:
        db.session.commit()
        print(f"DEBUG: Created new membership for user {user_id} in timeline {timeline_id}, role={role}, is_active_member={is_public}")
        
        # For private timelines, notify admins (future enhancement)
        if not is_public:
            # TODO: Add notification for admins/moderators
            return jsonify({"message": "Your request to join this timeline has been submitted", "role": role, "status": "pending"}), 201
        else:
            return jsonify({"message": "You have successfully joined this timeline", "role": role, "status": "joined"}), 201
    except Exception as e:
        db.session.rollback()
        print(f"ERROR: Failed to create membership: {str(e)}")
        return jsonify({"message": "Error processing your request", "status": "error"}), 500

@community_bp.route('/timelines/<int:timeline_id>/membership-status', methods=['GET'])
@jwt_required()
def check_membership_status(timeline_id):
    """Check if the current user is a member of the timeline and their role"""
    # Import models locally to avoid circular imports
    from app import Timeline, TimelineMember, User, db
    
    user_id = get_user_id()
    
    # SiteOwner (user ID 1) always has access to all timelines
    if user_id == 1:
        timeline = Timeline.query.get_or_404(timeline_id)
        return jsonify({
            "is_member": True,
            "role": "SiteOwner",
            "timeline_visibility": timeline.visibility
        }), 200
    
    # Check if user is the creator of this timeline
    timeline = Timeline.query.get_or_404(timeline_id)
    if timeline.created_by == user_id:
        # Check if creator is still an active member
        membership = TimelineMember.query.filter_by(
            timeline_id=timeline_id,
            user_id=user_id
        ).first()
        
        # If creator was removed, they need to rejoin
        if membership and not membership.is_active_member:
            return jsonify({
                "is_member": False,
                "role": None,
                "timeline_visibility": timeline.visibility,
                "is_creator": True,
                "was_removed": True
            }), 200
        
        # Creator is an admin member if active
        return jsonify({
            "is_member": True,
            "role": "admin",
            "timeline_visibility": timeline.visibility,
            "is_creator": True
        }), 200
        
    # For regular users, check database membership
    try:
        # Get membership
        membership = TimelineMember.query.filter_by(
            timeline_id=timeline_id,
            user_id=user_id
        ).first()
        
        # Explicitly check is_active_member flag
        is_active = bool(membership and membership.is_active_member)
        
        return jsonify({
            "is_member": is_active,
            "role": membership.role if (membership and is_active) else None,
            "timeline_visibility": timeline.visibility,
            "was_removed": bool(membership and not membership.is_active_member)
        }), 200
        
    except Exception as e:
        # Log the error but still return a safe response
        logger.error(f"Error checking membership status: {str(e)}")
        return jsonify({
            "is_member": False,
            "role": None,
            "timeline_visibility": "public"  # Default to public if we can't determine
        }), 200

@community_bp.route('/user/memberships', methods=['GET'])
@jwt_required()
def get_user_memberships():
    """Get all timeline memberships for the current user"""
    user_id = get_user_id()
    print(f"DEBUG: Fetching all memberships for user {user_id}")
    
    # Get all timelines where the user is a member
    memberships = TimelineMember.query.filter_by(user_id=user_id).all()
    
    # Get all timelines created by the user (they are implicitly members)
    created_timelines = Timeline.query.filter_by(created_by=user_id).all()
    created_timeline_ids = set(t.id for t in created_timelines)
    
    # Prepare the result
    result = []
    
    # Add memberships from the timeline_member table
    for membership in memberships:
        if membership.is_active_member:
            result.append({
                'timeline_id': membership.timeline_id,
                'role': membership.role,
                'joined_at': membership.joined_at.isoformat() if membership.joined_at else None
            })
    
    # Add timelines created by the user (if not already in the list)
    for timeline in created_timelines:
        # Check if this timeline is already in the result
        if not any(m['timeline_id'] == timeline.id for m in result):
            result.append({
                'timeline_id': timeline.id,
                'role': 'admin',  # Creator is always admin
                'joined_at': timeline.created_at.isoformat() if timeline.created_at else None
            })
    
    # Special case: SiteOwner (user ID 1) has access to all timelines
    if user_id == 1:
        print("DEBUG: SiteOwner detected, adding access to all timelines")
        # Get all timelines the SiteOwner doesn't already have explicit membership for
        all_timelines = Timeline.query.all()
        existing_timeline_ids = set(m['timeline_id'] for m in result)
        
        for timeline in all_timelines:
            if timeline.id not in existing_timeline_ids:
                result.append({
                    'timeline_id': timeline.id,
                    'role': 'SiteOwner',
                    'joined_at': None
                })
    
    print(f"DEBUG: Found {len(result)} memberships for user {user_id}")
    return jsonify(result), 200

@community_bp.route('/timelines/<int:timeline_id>/members/debug', methods=['GET'])
@jwt_required()
def debug_timeline_members(timeline_id):
    """Debug endpoint to log all members for a timeline"""
    user_id = get_user_id()
    print(f"DEBUG: Checking all members for timeline {timeline_id}, requested by user {user_id}")
    
    # Get timeline details
    timeline = Timeline.query.get_or_404(timeline_id)
    print(f"DEBUG: Timeline found: {timeline.id}, type: {timeline.timeline_type}, created by: {timeline.created_by}")
    
    # Get all members from database
    members = TimelineMember.query.filter_by(timeline_id=timeline_id).all()
    print(f"DEBUG: Found {len(members)} members in database for timeline {timeline_id}")
    
    # Log each member
    for member in members:
        user = User.query.get(member.user_id)
        username = user.username if user else 'Unknown'
        print(f"DEBUG: Member - user_id: {member.user_id}, username: {username}, role: {member.role}, joined_at: {member.joined_at}")
    
    # Check if current user is in the members list
    current_user_member = next((m for m in members if m.user_id == user_id), None)
    if current_user_member:
        print(f"DEBUG: Current user IS a member with role: {current_user_member.role}")
    else:
        print(f"DEBUG: Current user is NOT a member")
    
    # Check if creator is in the members list
    creator_member = next((m for m in members if m.user_id == timeline.created_by), None)
    if creator_member:
        print(f"DEBUG: Creator IS a member with role: {creator_member.role}")
    else:
        print(f"DEBUG: Creator is NOT a member")
    
    # Return the members list for API response
    member_schema = TimelineMemberSchema(many=True)
    return jsonify(member_schema.dump(members)), 200

@community_bp.route('/timelines/<int:timeline_id>/access-requests/<int:user_id>', methods=['PUT'])
@jwt_required()
def respond_to_access_request(timeline_id, user_id):
    """Approve or deny an access request to a timeline"""
    current_user_id = get_jwt_identity()
    print(f"DEBUG: User {current_user_id} responding to access request for user {user_id} in timeline {timeline_id}")
    
    # Check if current user is admin or moderator of the timeline
    current_user_membership = TimelineMember.query.filter_by(
        timeline_id=timeline_id, user_id=current_user_id
    ).first()
    
    if not current_user_membership or not current_user_membership.is_admin():
        print(f"DEBUG: User {current_user_id} is not authorized to respond to access requests")
        return jsonify({'error': 'Unauthorized: Only admins can respond to access requests'}), 403
    
    # Get the request data
    data = request.get_json()
    if not data or 'action' not in data:
        return jsonify({'error': 'Invalid request: action required'}), 400
        
    action = data['action']
    if action not in ['approve', 'deny']:
        return jsonify({'error': 'Invalid action: must be approve or deny'}), 400
    
    # Get the pending membership request
    membership = TimelineMember.query.filter_by(
        timeline_id=timeline_id, user_id=user_id, is_active_member=False
    ).first()
    
    if not membership:
        print(f"DEBUG: No pending request found for user {user_id} in timeline {timeline_id}")
        return jsonify({'error': 'No pending request found for this user'}), 404
    
    # Process the action
    try:
        if action == 'approve':
            print(f"DEBUG: Approving access request for user {user_id} in timeline {timeline_id}")
            membership.is_active_member = True
            # Keep the role as is, but ensure it's at least 'member' if it was 'pending'
            if membership.role == 'pending':
                membership.role = 'member'
            db.session.commit()
            return jsonify({
                'message': 'Access request approved', 
                'user_id': user_id,
                'status': 'approved'
            }), 200
        else:  # deny
            print(f"DEBUG: Denying access request for user {user_id} in timeline {timeline_id}")
            db.session.delete(membership)
            db.session.commit()
            return jsonify({
                'message': 'Access request denied', 
                'user_id': user_id,
                'status': 'denied'
            }), 200
    except Exception as e:
        db.session.rollback()
        print(f"ERROR: Failed to process access request: {str(e)}")
        return jsonify({'error': f'Failed to process access request: {str(e)}'}), 500       

@community_bp.route('/timelines/<int:timeline_id>/events/<int:event_id>/share', methods=['POST'])
@jwt_required()
def share_event(timeline_id, event_id):
    """Share an event to a community timeline"""
    user_id = get_user_id()
    
    # Check if event exists
    event = Event.query.get_or_404(event_id)
    
    # Get source timeline
    source_timeline = Timeline.query.get_or_404(event.timeline_id)
    
    # Get target timeline
    target_timeline = Timeline.query.get_or_404(timeline_id)
    
    # Check if user is a member of the target timeline
    membership = TimelineMember.query.filter_by(
        timeline_id=timeline_id, user_id=user_id
    ).first()
    
    if not membership or membership.role == 'pending':
        return jsonify({"error": "You are not a member of this timeline"}), 403
    
    # Check if event is already shared to this timeline
    existing = EventTimelineAssociation.query.filter_by(
        event_id=event_id, timeline_id=timeline_id
    ).first()
    
    if existing:
        return jsonify({"error": "Event is already shared to this timeline"}), 400
    
    # Create association
    association = EventTimelineAssociation(
        event_id=event_id,
        timeline_id=timeline_id,
        shared_by=user_id,
        shared_at=datetime.now(),
        source_timeline_id=source_timeline.id
    )
    
    db.session.add(association)
    db.session.commit()
    
    result = association_schema.dump(association)
    return jsonify(result), 201

@community_bp.route('/timelines/<int:timeline_id>/events/<int:event_id>/share', methods=['DELETE'])
@jwt_required()
def unshare_event(timeline_id, event_id):
    """Remove a shared event from a community timeline"""
    user_id = get_user_id()
    
    # Check if user is a member with appropriate permissions
    timeline, membership, has_access = check_timeline_access(timeline_id, 'moderator')
    
    if not has_access and not Event.query.get(event_id).created_by == user_id:
        return jsonify({"error": "Access denied"}), 403
    
    # Get the association
    association = EventTimelineAssociation.query.filter_by(
        event_id=event_id, timeline_id=timeline_id
    ).first_or_404()
    
    # Delete the association
    db.session.delete(association)
    db.session.commit()
    
    return jsonify({"message": "Event removed from timeline"}), 200

@community_bp.route('/timelines/<int:timeline_id>/shared-events', methods=['GET'])
@jwt_required()
def get_shared_events(timeline_id):
    """Get all events shared to a community timeline"""
    timeline, membership, has_access = check_timeline_access(timeline_id)
    
    if not has_access:
        return jsonify({"error": "Access denied"}), 403
    
    # Get all associations for this timeline
    associations = EventTimelineAssociation.query.filter_by(
        timeline_id=timeline_id
    ).all()
    
    result = associations_schema.dump(associations)
    return jsonify(result), 200

@community_bp.route('/timelines/<int:timeline_id>/blocked-members', methods=['GET'])
@jwt_required()
def get_blocked_members(timeline_id):
    """Get all blocked (inactive) members of a timeline"""
    # Check if user has access to view blocked members (admin or moderator)
    timeline, membership, has_access = check_timeline_access(timeline_id, 'moderator')
    
    if not has_access:
        return jsonify({"error": "Access denied. You need moderator privileges to view blocked members."}), 403
    
    try:
        # Get all inactive members with user information using SQLAlchemy
        blocked_members = db.session.query(
            TimelineMember, User
        ).join(
            User, TimelineMember.user_id == User.id
        ).filter(
            TimelineMember.timeline_id == timeline_id,
            TimelineMember.is_active_member == False  # Only get inactive members
        ).order_by(
            TimelineMember.joined_at.desc()  # Most recently blocked first
        ).all()
        
        result = []
        
        for member, user in blocked_members:
            # Get the action that blocked this member (if available)
            block_action = TimelineAction.query.filter_by(
                timeline_id=timeline_id,
                target_user_id=member.user_id,
                action_type='member_removed'
            ).order_by(TimelineAction.created_at.desc()).first()
            
            blocked_date = block_action.created_at if block_action else member.joined_at
            blocked_by = block_action.user_id if block_action else None
            reason = block_action.details if block_action else "Removed by administrator"
            
            member_data = {
                'id': member.id,
                'timeline_id': member.timeline_id,
                'user_id': member.user_id,
                'role': member.role,
                'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                'blocked_date': blocked_date.isoformat() if blocked_date else None,
                'blocked_by': blocked_by,
                'reason': reason,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'avatar_url': user.avatar_url,
                    'bio': user.bio
                }
            }
            result.append(member_data)
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error getting blocked members: {str(e)}")
        return jsonify({"error": str(e)}), 500

@community_bp.route('/timelines/<int:timeline_id>/reported-posts', methods=['GET'])
@jwt_required()
def get_reported_posts(timeline_id):
    """Get all reported posts for a timeline using TimelineAction model"""
    # Check if user has access to view reported posts (admin or moderator)
    timeline, membership, has_access = check_timeline_access(timeline_id, 'moderator')
    
    if not has_access:
        return jsonify({"error": "Access denied. You need moderator privileges to view reported posts."}), 403
    
    try:
        # Get all post report actions
        report_actions = TimelineAction.query.filter_by(
            timeline_id=timeline_id,
            action_type='post_reported'
        ).order_by(TimelineAction.created_at.desc()).all()
        
        result = []
        
        for action in report_actions:
            # Try to get the post and related users
            try:
                post_id = action.target_post_id
                if not post_id:
                    continue
                    
                post = Post.query.get(post_id)
                if not post:
                    continue
                    
                reporter = User.query.get(action.user_id)
                author = User.query.get(post.created_by)
                
                post_data = {
                    'id': post.id,
                    'timeline_id': post.timeline_id,
                    'content': post.content,
                    'title': post.title,
                    'created_at': post.created_at.isoformat() if post.created_at else None,
                    'reported_at': action.created_at.isoformat() if action.created_at else None,
                    'report_reason': action.details or 'Reported as inappropriate',
                    'author': {
                        'id': author.id if author else None,
                        'username': author.username if author else 'Deleted User',
                        'avatar_url': author.avatar_url if author else None
                    },
                    'reporter': {
                        'id': reporter.id if reporter else None,
                        'username': reporter.username if reporter else 'Unknown User',
                        'avatar_url': reporter.avatar_url if reporter else None
                    }
                }
                result.append(post_data)
            except Exception as inner_e:
                logger.error(f"Error processing reported post {action.target_post_id}: {str(inner_e)}")
                continue
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error getting reported posts: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Blueprint is registered in app.py
# Do not register here to avoid circular imports
