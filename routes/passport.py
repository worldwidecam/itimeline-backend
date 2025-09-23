"""
User Passport API routes for managing persistent membership data across devices.
"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import json
from datetime import datetime
import logging
from sqlalchemy import text
from utils.db_helper import get_db_engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
passport_bp = Blueprint('passport', __name__)

@passport_bp.route('/user/passport', methods=['GET'])
@jwt_required()
def get_user_passport():
    """
    Get the current user's passport containing all their timeline memberships.
    This is fetched whenever a user logs in from any device.
    """
    try:
        # Get current user ID from JWT
        current_user_id = get_jwt_identity()

        # Use low-level engine to avoid Flask-SQLAlchemy app-context dependency
        engine = get_db_engine()
        with engine.begin() as conn:
            # If the user_passport table does not exist, return empty defaults (avoid 500)
            try:
                reg = conn.execute(text("SELECT to_regclass('public.user_passport')")).first()
                table_exists = bool(reg and reg[0])
            except Exception as te:
                logger.info(f"passport: to_regclass check failed, assuming table missing ({te})")
                table_exists = False

            if not table_exists:
                return jsonify({
                    'memberships': [],
                    'preferences': {},
                    'last_updated': datetime.now().isoformat(),
                    'note': 'user_passport table not found; returning empty defaults'
                }), 200

            # Attempt to fetch the passport row (do not create on GET to avoid side effects)
            result = None
            try:
                result = conn.execute(
                    text('SELECT user_id, memberships_json, preferences_json, last_updated FROM user_passport WHERE user_id = :uid'),
                    {'uid': current_user_id}
                ).mappings().first()
            except Exception as e1:
                logger.info(f"passport: preferences_json not available or query failed ({e1}); trying legacy columns")
                try:
                    result = conn.execute(
                        text('SELECT user_id, memberships_json, last_updated FROM user_passport WHERE user_id = :uid'),
                        {'uid': current_user_id}
                    ).mappings().first()
                except Exception as e2:
                    logger.error(f"passport: failed to read passport row ({e2}); returning empty defaults")
                    result = None

            memberships = []
            if result and result.get('memberships_json'):
                try:
                    memberships = json.loads(result['memberships_json']) or []
                except Exception as je:
                    logger.info(f"passport: memberships_json parse error ({je}); using []")
                    memberships = []

            preferences = {}
            if result and result.get('preferences_json'):
                try:
                    preferences = json.loads(result['preferences_json']) or {}
                except Exception as pe:
                    logger.info(f"passport: preferences_json parse error ({pe}); using {{}}")
                    preferences = {}

            return jsonify({
                'memberships': memberships,
                'preferences': preferences,
                'last_updated': (result['last_updated'].isoformat() if result and result.get('last_updated') else datetime.now().isoformat())
            }), 200

    except Exception as e:
        logger.error(f"Error getting user passport: {str(e)}")
        return jsonify({'error': 'Failed to get user passport'}), 500
    finally:
        pass

@passport_bp.route('/user/passport/sync', methods=['POST'])
@jwt_required()
def sync_user_passport():
    """
    Sync the user's passport with the latest membership data.
    This is called after any membership changes (join/leave community).
    """
    try:
        # Get current user ID from JWT
        current_user_id = get_jwt_identity()

        memberships = []
        from app import db  # local import to avoid circular dependency
        with db.engine.begin() as conn:
            # Helper to check table existence safely
            def _exists(tbl: str) -> bool:
                try:
                    r = conn.execute(text("SELECT to_regclass(:t)"), { 't': f'public.{tbl}' }).first()
                    return bool(r and r[0])
                except Exception as _e:
                    return False

            has_tm = _exists('timeline_member')
            has_tl = _exists('timeline')
            has_passport = _exists('user_passport')

            # Build memberships defensively
            if has_tm and has_tl:
                # Active memberships
                try:
                    rows = conn.execute(text('''
                        SELECT tm.timeline_id, tm.role, tm.is_active_member, tm.joined_at,
                               t.name AS timeline_name, t.visibility, t.timeline_type
                        FROM timeline_member tm
                        JOIN timeline t ON tm.timeline_id = t.id
                        WHERE tm.user_id = :uid AND tm.is_active_member = TRUE
                    '''), {'uid': current_user_id}).mappings().all()
                    for row in rows:
                        memberships.append({
                            'timeline_id': row['timeline_id'],
                            'role': row['role'],
                            'is_active_member': bool(row['is_active_member']),
                            'isMember': bool(row['is_active_member']),
                            'joined_at': row['joined_at'].isoformat() if row['joined_at'] else None,
                            'timeline_name': row['timeline_name'],
                            'visibility': row['visibility'],
                            'timeline_type': row['timeline_type']
                        })
                except Exception as e_am:
                    logger.info(f"passport.sync: skipping active memberships ({e_am})")

                # Timelines created by the user (implicit admin)
                try:
                    created_rows = conn.execute(text('''
                        SELECT id AS timeline_id, name AS timeline_name, visibility, timeline_type, created_at
                        FROM timeline
                        WHERE created_by = :uid AND id NOT IN (
                            SELECT timeline_id FROM timeline_member WHERE user_id = :uid
                        )
                    '''), {'uid': current_user_id}).mappings().all()
                    for row in created_rows:
                        memberships.append({
                            'timeline_id': row['timeline_id'],
                            'role': 'admin',
                            'is_active_member': True,
                            'joined_at': row['created_at'].isoformat() if row['created_at'] else None,
                            'timeline_name': row['timeline_name'],
                            'visibility': row['visibility'],
                            'timeline_type': row['timeline_type'],
                            'is_creator': True
                        })
                except Exception as e_cr:
                    logger.info(f"passport.sync: skipping created timelines ({e_cr})")

                # SiteOwner (user ID 1) access to all timelines
                if has_tl and int(current_user_id) == 1:
                    try:
                        so_rows = conn.execute(text('''
                            SELECT id AS timeline_id, name AS timeline_name, visibility, timeline_type, created_at
                            FROM timeline
                            WHERE id NOT IN (
                                SELECT timeline_id FROM timeline_member WHERE user_id = 1
                            )
                        ''')).mappings().all()
                        for row in so_rows:
                            memberships.append({
                                'timeline_id': row['timeline_id'],
                                'role': 'SiteOwner',
                                'is_active_member': True,
                                'isMember': True,
                                'joined_at': row['created_at'].isoformat() if row['created_at'] else None,
                                'timeline_name': row['timeline_name'],
                                'visibility': row['visibility'],
                                'timeline_type': row['timeline_type'],
                                'is_site_owner': True
                            })
                    except Exception as e_so:
                        logger.info(f"passport.sync: skipping site-owner expansion ({e_so})")

            # Upsert passport only if table exists
            if has_passport:
                try:
                    conn.execute(text('''
                        INSERT INTO user_passport (user_id, memberships_json, last_updated)
                        VALUES (:uid, :mjson, :lu)
                        ON CONFLICT (user_id)
                        DO UPDATE SET memberships_json = EXCLUDED.memberships_json, last_updated = EXCLUDED.last_updated
                    '''), {
                        'uid': current_user_id,
                        'mjson': json.dumps(memberships),
                        'lu': datetime.now()
                    })
                except Exception as e_up:
                    logger.info(f"passport.sync: upsert skipped ({e_up})")

        return jsonify({
            'memberships': memberships,
            'last_updated': datetime.now().isoformat(),
            'message': 'Passport synced (best-effort)'
        }), 200
        
    except Exception as e:
        logger.error(f"Error syncing user passport: {str(e)}")
        return jsonify({'error': 'Failed to sync user passport'}), 500

@passport_bp.route('/user/preferences', methods=['PUT'])
@jwt_required()
def update_user_preferences():
    """
    Update the current user's preferences stored in the passport.
    Allowed fields: theme ('dark'|'light'), email_blur (bool)
    """
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json(silent=True) or {}

        # Whitelist allowed keys and normalize values
        allowed = {}
        if 'theme' in data:
            theme_val = str(data.get('theme', '')).lower()
            if theme_val in ('dark', 'light'):
                allowed['theme'] = theme_val
        if 'email_blur' in data:
            allowed['email_blur'] = bool(data.get('email_blur'))

        if not allowed:
            return jsonify({'message': 'No valid preference fields provided'}), 400

        engine = get_db_engine()
        with engine.begin() as conn:
            # Ensure passport row exists
            conn.execute(
                text('''
                    INSERT INTO user_passport (user_id, memberships_json, preferences_json, last_updated)
                    VALUES (:uid, :mjson, :pjson, :lu)
                    ON CONFLICT (user_id) DO NOTHING
                '''),
                {
                    'uid': current_user_id,
                    'mjson': '[]',
                    'pjson': '{}',
                    'lu': datetime.now()
                }
            )

            # Load existing preferences
            row = conn.execute(
                text('SELECT preferences_json FROM user_passport WHERE user_id = :uid'),
                {'uid': current_user_id}
            ).mappings().first()
            current_prefs = {}
            if row and row.get('preferences_json'):
                try:
                    current_prefs = json.loads(row['preferences_json']) or {}
                except json.JSONDecodeError:
                    current_prefs = {}

            # Merge
            current_prefs.update(allowed)

            # Persist
            conn.execute(
                text('''
                    UPDATE user_passport
                    SET preferences_json = :pjson, last_updated = :lu
                    WHERE user_id = :uid
                '''),
                {
                    'uid': current_user_id,
                    'pjson': json.dumps(current_prefs),
                    'lu': datetime.now()
                }
            )

        return jsonify({'message': 'Preferences updated', 'preferences': current_prefs}), 200
    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}")
        return jsonify({'error': 'Failed to update preferences'}), 500
