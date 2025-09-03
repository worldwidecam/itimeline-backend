"""
Community Timeline API Routes

This module contains all routes related to community timelines, including:
- Creating and managing community timelines
- Managing timeline members and roles
- Handling access requests for private timelines
- Sharing posts between communities
"""

from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError
import sqlite3
import logging

# Create blueprint first, before any circular imports can happen
community_bp = Blueprint('community', __name__)

# Module logger
logger = logging.getLogger(__name__)

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

def get_role_rank(role):
    """Get numeric rank for role comparison. Higher number = higher rank."""
    role_hierarchy = {
        'member': 1,
        'moderator': 2, 
        'admin': 3,
        'SiteOwner': 4
    }
    return role_hierarchy.get(role, 0)

def can_act_on_member(actor_id, actor_role, target_id, target_role, timeline_created_by):
    """Check if actor can perform action on target based on rank hierarchy.
    
    Rules:
    - SiteOwner > Creator/Admin > Moderator > Member
    - Timeline creator gets admin-level rank for comparisons
    - No self-actions
    - Equal rank cannot act on equal rank
    - Cannot act on SiteOwner (user 1)
    
    Returns: (can_act: bool, reason: str)
    """
    actor_id = int(actor_id)
    target_id = int(target_id)
    
    # Cannot act on SiteOwner
    if target_id == 1:
        return False, "Cannot act on site owner"
    
    # Cannot act on yourself
    if actor_id == target_id:
        return False, "Cannot act on yourself"
    
    # SiteOwner can act on anyone (except themselves, checked above)
    if actor_id == 1:
        return True, "SiteOwner privilege"
    
    # Timeline creator gets admin-level rank for this timeline
    effective_actor_role = actor_role
    if actor_id == timeline_created_by and actor_role != 'SiteOwner':
        effective_actor_role = 'admin'
    
    effective_target_role = target_role
    if target_id == timeline_created_by and target_role != 'SiteOwner':
        effective_target_role = 'admin'
    
    actor_rank = get_role_rank(effective_actor_role)
    target_rank = get_role_rank(effective_target_role)
    
    if actor_rank > target_rank:
        return True, f"Rank check passed: {effective_actor_role}({actor_rank}) > {effective_target_role}({target_rank})"
    else:
        return False, f"Insufficient rank: {effective_actor_role}({actor_rank}) <= {effective_target_role}({target_rank})"

def check_timeline_access(timeline_id, required_role=None):
    """
    Check if the current user has access to the timeline
    
    Args:
        timeline_id: ID of the timeline to check
        required_role: Minimum role required (None = any member, 'moderator', 'admin')
        
    Returns:
        tuple: (timeline, membership, has_access)
    """
    # Local imports to avoid circular import issues
    from app import db
    from sqlalchemy import text
    user_id = get_user_id()
    # Normalize to int for reliable comparisons
    try:
        user_id_int = int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        user_id_int = user_id
    
    try:
        # Use raw SQL with db.engine to avoid ORM binding issues
        with db.engine.begin() as conn:
            # Get timeline information
            timeline_row = conn.execute(
                text("SELECT id, created_by, name, description, visibility FROM timeline WHERE id = :tid"),
                {"tid": timeline_id}
            ).mappings().first()
            if not timeline_row:
                return None, None, False
            
            # SiteOwner (user ID 1) always has access to any timeline
            if user_id_int == 1:
                membership_row = conn.execute(
                    text("SELECT * FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid"),
                    {"tid": timeline_id, "uid": user_id_int}
                ).mappings().first()
                return timeline_row, membership_row, True
            
            # Timeline creator should have admin-level access even without an explicit membership row
            if timeline_row["created_by"] == user_id_int:
                # Best effort: see if they also have a membership row (active or not)
                membership_row = conn.execute(
                    text("SELECT * FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid"),
                    {"tid": timeline_id, "uid": user_id_int}
                ).mappings().first()
                # Creator can perform moderator/admin actions
                return timeline_row, membership_row, True
            
            # Check if user is an active member of the timeline
            membership_row = conn.execute(
                text("SELECT * FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid AND is_active_member = TRUE"),
                {"tid": timeline_id, "uid": user_id_int}
            ).mappings().first()
            
            # If not a member, no access
            if not membership_row:
                return timeline_row, None, False
            
            # Check if user has the required role
            if required_role:
                role_hierarchy = {'member': 1, 'moderator': 2, 'admin': 3, 'SiteOwner': 4}
                user_role_level = role_hierarchy.get(membership_row["role"], 0)
                required_role_level = role_hierarchy.get(required_role, 0)
                has_access = user_role_level >= required_role_level
            else:
                has_access = True
            
            return timeline_row, membership_row, has_access
        
    except Exception as e:
        logger.error(f"Error checking timeline access: {str(e)}")
        raise e

# Routes
@community_bp.route('/timelines/community', methods=['POST'])
@jwt_required()
def create_community_timeline():
    """Create a new community timeline"""
    # Use the single bound SQLAlchemy instance and models from app
    from app import db, Timeline, TimelineMember
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

@community_bp.route('/timelines/<int:timeline_id>/members', methods=['GET', 'OPTIONS'])
@cross_origin(
    origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://i-timeline.com',
        'https://www.i-timeline.com'
    ],
    methods=['GET', 'OPTIONS'],
    allow_headers=['Content-Type', 'Authorization', 'Cache-Control', 'Pragma', 'Expires'],
    supports_credentials=True,
)
@jwt_required()
def get_timeline_members(timeline_id):
    """Get all active members of a timeline using raw SQL to avoid ORM binding issues"""
    try:
        logger.info(f"get_timeline_members: start for timeline_id={timeline_id}")
        # IMPORTANT: Avoid importing db from app unless absolutely necessary to prevent
        # creating a second Flask app/SQLAlchemy instance. Prefer pulling from current_app.
        from flask import current_app
        sa_ext = current_app.extensions.get('sqlalchemy')
        engine = None
        if sa_ext is None:
            logger.warning("get_timeline_members: sqlalchemy extension not found on current_app.extensions")
        else:
            # Try common attribute shapes across Flask-SQLAlchemy versions
            if hasattr(sa_ext, 'db') and hasattr(sa_ext.db, 'engine'):
                engine = sa_ext.db.engine
                logger.info("get_timeline_members: using engine via sa_ext.db.engine")
            elif hasattr(sa_ext, 'engine'):
                engine = sa_ext.engine
                logger.info("get_timeline_members: using engine via sa_ext.engine")
            elif hasattr(sa_ext, 'engines'):
                try:
                    engine = sa_ext.engines[current_app]
                    logger.info("get_timeline_members: using engine via sa_ext.engines[current_app]")
                except Exception as e:
                    logger.warning(f"get_timeline_members: failed sa_ext.engines lookup: {e}")

        # Last-resort fallback: import db from app (may risk dual instances, logged as warning)
        if engine is None:
            try:
                from app import db as app_db
                engine = app_db.engine
                logger.warning("get_timeline_members: fell back to importing db from app (monitor for binding issues)")
            except Exception as e:
                logger.exception(f"get_timeline_members: failed to obtain engine from app db: {e}")
                raise

        from sqlalchemy import text
        logger.info("get_timeline_members: imported sqlalchemy.text")
        
        result = []
        
        logger.info("get_timeline_members: engine ready, beginning connection")
        with engine.begin() as conn:
            logger.info("get_timeline_members: connection begun")
            # Get timeline details for creator and created_at
            logger.info("get_timeline_members: querying timeline meta")
            timeline_row = conn.execute(
                text("""
                    SELECT id, created_by, created_at 
                    FROM timeline 
                    WHERE id = :tid
                """),
                {"tid": timeline_id}
            ).mappings().first()
            
            if not timeline_row:
                logger.warning(f"get_timeline_members: timeline {timeline_id} not found")
                return jsonify({"error": "Timeline not found"}), 404
            
            # Fetch active members (excluding blocked)
            logger.info("get_timeline_members: querying active members")
            rows = conn.execute(text("""
                SELECT tm.id, tm.timeline_id, tm.user_id, tm.role, tm.is_active_member,
                       tm.joined_at, tm.invited_by,
                       u.id AS user_id_u, u.username, u.email, u.avatar_url, u.bio
                FROM timeline_member tm
                JOIN "user" u ON tm.user_id = u.id
                WHERE tm.timeline_id = :tid
                  AND tm.is_active_member = TRUE
                  AND (tm.is_blocked IS NULL OR tm.is_blocked = FALSE)
            """), {"tid": timeline_id}).mappings().all()
            
            logger.info(f"get_timeline_members: fetched {len(rows)} db members")
            for row in rows:
                member_data = {
                    'id': row['id'],
                    'timeline_id': row['timeline_id'],
                    'user_id': row['user_id'],
                    'role': row['role'],
                    'is_active_member': bool(row['is_active_member']),
                    'joined_at': row['joined_at'].isoformat() if row['joined_at'] else None,
                    'invited_by': row['invited_by'],
                    'user': {
                        'id': row['user_id_u'],
                        'username': row['username'],
                        'email': row['email'],
                        'avatar_url': row['avatar_url'],
                        'bio': row['bio']
                    }
                }
                result.append(member_data)
            
            # Add SiteOwner (user ID 1) if not already present
            site_owner_present = any(m['user_id'] == 1 for m in result)
            if not site_owner_present:
                logger.info("get_timeline_members: adding SiteOwner virtual member")
                so_row = conn.execute(
                    text("SELECT id, username, email, avatar_url, bio FROM ""user"" WHERE id = 1")
                ).mappings().first()
                if so_row:
                    result.append({
                        'id': None,
                        'timeline_id': timeline_id,
                        'user_id': 1,
                        'role': 'SiteOwner',
                        'is_active_member': True,
                        'joined_at': timeline_row['created_at'].isoformat() if timeline_row['created_at'] else None,
                        'invited_by': None,
                        'user': {
                            'id': so_row['id'],
                            'username': so_row['username'],
                            'email': so_row['email'],
                            'avatar_url': so_row['avatar_url'],
                            'bio': so_row['bio']
                        }
                    })
            
            # Add Creator if not already present and not SiteOwner
            creator_id = timeline_row['created_by']
            if creator_id and creator_id != 1 and not any(m['user_id'] == creator_id for m in result):
                logger.info(f"get_timeline_members: adding creator virtual member user_id={creator_id}")
                creator_row = conn.execute(
                    text("SELECT id, username, email, avatar_url, bio FROM ""user"" WHERE id = :uid"),
                    {"uid": creator_id}
                ).mappings().first()
                if creator_row:
                    result.append({
                        'id': None,
                        'timeline_id': timeline_id,
                        'user_id': creator_id,
                        'role': 'admin',
                        'is_active_member': True,
                        'joined_at': timeline_row['created_at'].isoformat() if timeline_row['created_at'] else None,
                        'invited_by': None,
                        'user': {
                            'id': creator_row['id'],
                            'username': creator_row['username'],
                            'email': creator_row['email'],
                            'avatar_url': creator_row['avatar_url'],
                            'bio': creator_row['bio']
                        }
                    })
        
        logger.info(f"get_timeline_members: returning {len(result)} members (including virtual)")
        return jsonify(result), 200
    except Exception as e:
        logger.exception(f"Error getting timeline members: {str(e)}")
        return jsonify({"error": str(e)}), 500

 

@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>/block', methods=['OPTIONS'], endpoint='community_block_member_preflight')
@cross_origin(
    origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://i-timeline.com',
        'https://www.i-timeline.com'
    ],
    methods=['OPTIONS'],
    allow_headers=['Content-Type', 'Authorization', 'Cache-Control', 'Pragma', 'Expires'],
    supports_credentials=True,
)
def preflight_block_member(timeline_id, user_id):
    return ('', 204)


@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>/block', methods=['POST'], endpoint='community_block_member_v2')
@cross_origin(
    origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://i-timeline.com',
        'https://www.i-timeline.com'
    ],
    methods=['POST'],
    allow_headers=['Content-Type', 'Authorization', 'Cache-Control', 'Pragma', 'Expires'],
    supports_credentials=True,
)
@jwt_required()
def block_timeline_member_v2(timeline_id, user_id):
    """Block a member: set is_blocked=True and is_active_member=False"""
    from app import db, TimelineMember
    from sqlalchemy import text
    
    try:
        current_user_id = int(get_user_id())
        user_id = int(user_id)
        timeline_id = int(timeline_id)
        
        data = request.get_json(silent=True) or {}
        reason = data.get('reason')
        
        with db.engine.begin() as conn:
            # Get timeline and actor/target member info
            timeline_row = conn.execute(
                text("SELECT created_by FROM timeline WHERE id = :tid"),
                {"tid": timeline_id}
            ).mappings().first()
            
            if not timeline_row:
                return jsonify({"error": "Timeline not found"}), 404
            
            timeline_created_by = timeline_row['created_by']
            
            # Get actor role
            if current_user_id == 1:
                actor_role = 'SiteOwner'
            elif current_user_id == timeline_created_by:
                actor_role = 'admin'
            else:
                actor_membership = conn.execute(
                    text("SELECT role FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid AND is_active_member = TRUE"),
                    {"tid": timeline_id, "uid": current_user_id}
                ).scalar()
                if not actor_membership:
                    return jsonify({"error": "Access denied - not a member"}), 403
                actor_role = actor_membership
            
            # Get target role
            if user_id == 1:
                target_role = 'SiteOwner'
            elif user_id == timeline_created_by:
                target_role = 'admin'
            else:
                target_membership = conn.execute(
                    text("SELECT role FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid"),
                    {"tid": timeline_id, "uid": user_id}
                ).scalar()
                if not target_membership:
                    return jsonify({"error": "Target member not found"}), 404
                target_role = target_membership
            
            # Check if action is allowed
            can_act, perm_reason = can_act_on_member(current_user_id, actor_role, user_id, target_role, timeline_created_by)
            
            logger.info(f"Block action: actor_id={current_user_id}, actor_role={actor_role}, target_id={user_id}, target_role={target_role}, allowed={can_act}, reason={perm_reason}")
            
            if not can_act:
                return jsonify({"error": f"Access denied: {perm_reason}"}), 403
            
            # Check if already blocked
            current_status = conn.execute(
                text("SELECT is_blocked FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid"),
                {"tid": timeline_id, "uid": user_id}
            ).scalar()
            
            if current_status:
                return jsonify({"message": "Already blocked"}), 200
            
            # Perform the block
            result = conn.execute(
                text("""
                    UPDATE timeline_member 
                    SET is_blocked = TRUE,
                        is_active_member = FALSE,
                        blocked_at = NOW(),
                        blocked_reason = :reason
                    WHERE timeline_id = :tid AND user_id = :uid
                """),
                {"tid": timeline_id, "uid": user_id, "reason": reason}
            )
            
            if result.rowcount == 0:
                return jsonify({"error": "Member not found"}), 404
        
        return jsonify({
            'message': 'Member blocked',
            'user_id': user_id,
            'timeline_id': timeline_id,
            'is_blocked': True,
            'is_active_member': False,
            'action': 'block'
        }), 200
        
    except Exception as e:
        logger.error(f"Error blocking member: {str(e)}")
        return jsonify({"error": str(e)}), 500

@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>/unblock', methods=['OPTIONS'], endpoint='community_unblock_member_preflight')
@cross_origin(
    origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://i-timeline.com',
        'https://www.i-timeline.com'
    ],
    methods=['OPTIONS'],
    allow_headers=['Content-Type', 'Authorization', 'Cache-Control', 'Pragma', 'Expires'],
    supports_credentials=True,
)
def preflight_unblock_member(timeline_id, user_id):
    return ('', 204)


@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>/unblock', methods=['POST'], endpoint='community_unblock_member_v2')
@cross_origin(
    origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://i-timeline.com',
        'https://www.i-timeline.com'
    ],
    methods=['POST'],
    allow_headers=['Content-Type', 'Authorization', 'Cache-Control', 'Pragma', 'Expires'],
    supports_credentials=True,
)
@jwt_required()
def unblock_timeline_member_v2(timeline_id, user_id):
    """Unblock a member: set is_blocked=False and is_active_member=True"""
    from app import db, TimelineMember
    from sqlalchemy import text
    
    try:
        current_user_id = int(get_user_id())
        user_id = int(user_id)
        timeline_id = int(timeline_id)
        
        with db.engine.begin() as conn:
            # Get timeline and actor/target member info
            timeline_row = conn.execute(
                text("SELECT created_by FROM timeline WHERE id = :tid"),
                {"tid": timeline_id}
            ).mappings().first()
            
            if not timeline_row:
                return jsonify({"error": "Timeline not found"}), 404
            
            timeline_created_by = timeline_row['created_by']
            
            # Get actor role
            if current_user_id == 1:
                actor_role = 'SiteOwner'
            elif current_user_id == timeline_created_by:
                actor_role = 'admin'
            else:
                actor_membership = conn.execute(
                    text("SELECT role FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid AND is_active_member = TRUE"),
                    {"tid": timeline_id, "uid": current_user_id}
                ).scalar()
                if not actor_membership:
                    return jsonify({"error": "Access denied - not a member"}), 403
                actor_role = actor_membership
            
            # Get target role (from blocked member record)
            if user_id == 1:
                target_role = 'SiteOwner'
            elif user_id == timeline_created_by:
                target_role = 'admin'
            else:
                target_membership = conn.execute(
                    text("SELECT role FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid"),
                    {"tid": timeline_id, "uid": user_id}
                ).scalar()
                if not target_membership:
                    return jsonify({"error": "Target member not found"}), 404
                target_role = target_membership
            
            # Check if action is allowed
            can_act, perm_reason = can_act_on_member(current_user_id, actor_role, user_id, target_role, timeline_created_by)
            
            logger.info(f"Unblock action: actor_id={current_user_id}, actor_role={actor_role}, target_id={user_id}, target_role={target_role}, allowed={can_act}, reason={perm_reason}")
            
            if not can_act:
                return jsonify({"error": f"Access denied: {perm_reason}"}), 403
            
            # Check current status
            current_member = conn.execute(
                text("SELECT is_blocked, is_active_member FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid"),
                {"tid": timeline_id, "uid": user_id}
            ).mappings().first()
            
            if not current_member:
                return jsonify({"error": "Member not found"}), 404
            
            if not current_member['is_blocked'] and current_member['is_active_member']:
                return jsonify({"message": "Already active"}), 200
            
            # Perform the unblock (restore to active membership)
            result = conn.execute(
                text("""
                    UPDATE timeline_member 
                    SET is_blocked = FALSE,
                        is_active_member = TRUE,
                        blocked_reason = NULL
                    WHERE timeline_id = :tid AND user_id = :uid
                """),
                {"tid": timeline_id, "uid": user_id}
            )
            
            if result.rowcount == 0:
                return jsonify({"error": "Member not found"}), 404
        
        return jsonify({
            'message': 'Member unblocked',
            'user_id': user_id,
            'timeline_id': timeline_id,
            'is_blocked': False,
            'is_active_member': True,
            'action': 'unblock'
        }), 200
        
    except Exception as e:
        logger.error(f"Error unblocking member: {str(e)}")
        return jsonify({"error": str(e)}), 500

@community_bp.route('/timelines/<int:timeline_id>/members', methods=['POST'])
@jwt_required()
def add_timeline_member(timeline_id):
    """Add a new member to a timeline"""
    from app import db, TimelineMember, User
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
@cross_origin(
    origins=[
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'https://i-timeline.com',
        'https://www.i-timeline.com'
    ],
    methods=['DELETE', 'OPTIONS'],
    allow_headers=['Content-Type', 'Authorization', 'Cache-Control', 'Pragma', 'Expires'],
    supports_credentials=True,
)
@jwt_required()
def remove_timeline_member_v2(timeline_id, user_id):
    """Remove v2: Kick member (soft remove) - set is_active_member=FALSE, is_blocked=FALSE"""
    from app import db
    from sqlalchemy import text
    
    try:
        raw_identity = get_user_id()
        logger.info(f"remove_timeline_member_v2: raw_identity={raw_identity}, timeline_id={timeline_id}, target_user_id={user_id}")
        current_user_id = int(raw_identity)
        user_id = int(user_id)
        timeline_id = int(timeline_id)
        
        # Obtain engine in a version-safe way (mirror get_timeline_members)
        from flask import current_app
        sa_ext = current_app.extensions.get('sqlalchemy')
        engine = None
        if sa_ext is None:
            logger.warning("remove_timeline_member_v2: sqlalchemy extension not found on current_app.extensions")
        else:
            if hasattr(sa_ext, 'db') and hasattr(sa_ext.db, 'engine'):
                engine = sa_ext.db.engine
                logger.info("remove_timeline_member_v2: using engine via sa_ext.db.engine")
            elif hasattr(sa_ext, 'engine'):
                engine = sa_ext.engine
                logger.info("remove_timeline_member_v2: using engine via sa_ext.engine")
            elif hasattr(sa_ext, 'engines'):
                try:
                    engine = sa_ext.engines[current_app]
                    logger.info("remove_timeline_member_v2: using engine via sa_ext.engines[current_app]")
                except Exception as e:
                    logger.warning(f"remove_timeline_member_v2: failed sa_ext.engines lookup: {e}")

        if engine is None:
            try:
                from app import db as app_db
                engine = app_db.engine
                logger.warning("remove_timeline_member_v2: fell back to importing db from app (monitor for binding issues)")
            except Exception as e:
                logger.exception(f"remove_timeline_member_v2: failed to obtain engine from app db: {e}")
                raise

        # Single transaction with rank-based permission check
        with engine.begin() as conn:
            # Get timeline and actor/target member info
            timeline_row = conn.execute(
                text("SELECT created_by FROM timeline WHERE id = :tid"),
                {"tid": timeline_id}
            ).mappings().first()
            
            if not timeline_row:
                return jsonify({"error": "Timeline not found"}), 404
            
            timeline_created_by = timeline_row['created_by']
            
            # Get actor role
            if current_user_id == 1:
                actor_role = 'SiteOwner'
            elif current_user_id == timeline_created_by:
                actor_role = 'admin'  # Creator gets admin rank
            else:
                actor_membership = conn.execute(
                    text("SELECT role FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid AND is_active_member = TRUE"),
                    {"tid": timeline_id, "uid": current_user_id}
                ).scalar()
                if not actor_membership:
                    return jsonify({"error": "Access denied - not a member"}), 403
                actor_role = actor_membership
            
            # Get target role
            if user_id == 1:
                target_role = 'SiteOwner'
            elif user_id == timeline_created_by:
                target_role = 'admin'
            else:
                target_membership = conn.execute(
                    text("SELECT role FROM timeline_member WHERE timeline_id = :tid AND user_id = :uid"),
                    {"tid": timeline_id, "uid": user_id}
                ).scalar()
                if not target_membership:
                    return jsonify({"error": "Target member not found"}), 404
                target_role = target_membership
            
            # Check if action is allowed
            can_act, reason = can_act_on_member(current_user_id, actor_role, user_id, target_role, timeline_created_by)
            
            logger.info(f"Remove action: actor_id={current_user_id}, actor_role={actor_role}, target_id={user_id}, target_role={target_role}, allowed={can_act}, reason={reason}")
            
            if not can_act:
                return jsonify({"error": f"Access denied: {reason}"}), 403
            
            # Perform soft kick: remove from active membership but don't block
            result = conn.execute(
                text("""
                    UPDATE timeline_member 
                    SET is_active_member = FALSE
                    WHERE timeline_id = :tid AND user_id = :uid
                """),
                {"tid": timeline_id, "uid": user_id}
            )
            
            if result.rowcount == 0:
                return jsonify({"error": "Member not found"}), 404
        
        return jsonify({
            "message": "Member kicked successfully",
            "removed_user_id": user_id,
            "removed_by": current_user_id,
            "action": "kick"
        }), 200
        
    except Exception as e:
        logger.exception(f"Error in remove_timeline_member_v2: {str(e)}")
        return jsonify({"error": f"Error removing member: {str(e)}"}), 500

@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>/role', methods=['PUT'])
@jwt_required()
def update_member_role(timeline_id, user_id):
    """Update a member's role in a timeline"""
    from app import db, TimelineMember
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
    from app import db, Timeline
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
    from app import db, Timeline, TimelineMember
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
    from app import TimelineMember, Timeline
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
    from app import Timeline, TimelineMember, User
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
    from app import db, Event, Timeline, EventTimelineAssociation
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
    from app import db, Event, EventTimelineAssociation
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
    from app import EventTimelineAssociation
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
    """Get all blocked members of a timeline using raw SQL."""
    from app import db
    from sqlalchemy import text
    # Check if user has access to view blocked members (admin or moderator)
    timeline, membership, has_access = check_timeline_access(timeline_id, 'moderator')
    
    if not has_access:
        return jsonify({"error": "Access denied. You need moderator privileges to view blocked members."}), 403
    
    try:
        with db.engine.begin() as conn:
            blocked_members_data = conn.execute(
                text("""
                    SELECT tm.id, tm.timeline_id, tm.user_id, tm.role, tm.is_active_member,
                           tm.is_blocked, tm.blocked_at, tm.blocked_reason, tm.joined_at, tm.invited_by,
                           u.id as user_id_u, u.username, u.email, u.avatar_url, u.bio
                    FROM timeline_member tm
                    JOIN "user" u ON tm.user_id = u.id
                    WHERE tm.timeline_id = :tid AND tm.is_blocked = TRUE
                    ORDER BY tm.blocked_at DESC NULLS LAST
                """),
                {"tid": timeline_id}
            ).mappings().all()
            
            result = []
            for row in blocked_members_data:
                member_data = {
                    'id': row['id'],
                    'timeline_id': row['timeline_id'],
                    'user_id': row['user_id'],
                    'role': row['role'],
                    'is_active_member': bool(row['is_active_member']),
                    'is_blocked': bool(row['is_blocked']),
                    'blocked_at': row['blocked_at'].isoformat() if row['blocked_at'] else None,
                    'blocked_reason': row['blocked_reason'],
                    'joined_at': row['joined_at'].isoformat() if row['joined_at'] else None,
                    'invited_by': row['invited_by'],
                    'user': {
                        'id': row['user_id_u'],
                        'username': row['username'],
                        'email': row['email'],
                        'avatar_url': row['avatar_url'],
                        'bio': row['bio']
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
    from app import TimelineAction, Post, User
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
