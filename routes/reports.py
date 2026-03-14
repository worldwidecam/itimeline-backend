from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, verify_jwt_in_request, get_jwt_identity
from datetime import datetime, timezone, timedelta
import logging
from sqlalchemy import text
from utils.db_helper import get_db_engine

# We import helpers from community routes for consistent access control semantics
from routes.community import check_timeline_access, get_user_id

reports_bp = Blueprint('reports', __name__)
logger = logging.getLogger(__name__)

STATUS_HEADER_WORD_LIMIT = 4
STATUS_HEADER_MAX_CHARS = 120
STATUS_BODY_MAX_CHARS = 320


def _ensure_reports_table(engine):
    """Create the reports table and indexes if they don't already exist.
    Non-destructive and safe to call repeatedly.
    """
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id SERIAL PRIMARY KEY,
                timeline_id INTEGER NOT NULL,
                event_id INTEGER NULL,
                reporter_id INTEGER NULL,
                report_type VARCHAR(16) NOT NULL DEFAULT 'post',
                reported_user_id INTEGER NULL,
                reported_timeline_id INTEGER NULL,
                reason TEXT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                assigned_to INTEGER NULL,
                resolution VARCHAR(16) NULL,
                verdict TEXT NULL,
                escalation_type VARCHAR(16) NULL,
                escalation_summary TEXT NULL,
                escalated_by INTEGER NULL,
                escalated_at TIMESTAMP WITHOUT TIME ZONE NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                resolved_at TIMESTAMP WITHOUT TIME ZONE NULL
            );
            """
        ))
        # Basic indexes for filters
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_reports_timeline_status ON reports (timeline_id, status);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_reports_status_created_at ON reports (status, created_at DESC);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_reports_event_id ON reports (event_id);"))
        conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS report_type VARCHAR(16) NOT NULL DEFAULT 'post';"))
        conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS reported_user_id INTEGER NULL;"))
        conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS reported_timeline_id INTEGER NULL;"))
        conn.execute(text("ALTER TABLE reports ALTER COLUMN event_id DROP NOT NULL;"))
        conn.execute(text("ALTER TABLE reports ALTER COLUMN resolution TYPE VARCHAR(64);"))
        conn.execute(text("UPDATE reports SET report_type = 'post' WHERE report_type IS NULL;"))


def _ensure_timeline_status_message_table(engine):
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS timeline_status_message (
                id SERIAL PRIMARY KEY,
                timeline_id INTEGER NOT NULL,
                status_type VARCHAR(16) NULL,
                status_header VARCHAR(120) NULL,
                status_body TEXT NULL,
                is_active BOOLEAN NOT NULL DEFAULT FALSE,
                updated_by INTEGER NULL,
                updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                CONSTRAINT fk_timeline_status_message_timeline FOREIGN KEY (timeline_id) REFERENCES timeline(id) ON DELETE CASCADE,
                CONSTRAINT fk_timeline_status_message_user FOREIGN KEY (updated_by) REFERENCES "user"(id) ON DELETE SET NULL,
                CONSTRAINT uq_timeline_status_message_timeline UNIQUE (timeline_id)
            );
            """
        ))
        conn.execute(text(
            """
            CREATE INDEX IF NOT EXISTS idx_timeline_status_message_active
                ON timeline_status_message (timeline_id, is_active);
            """
        ))

        # Skip runtime schema mutation via DO $$ to avoid transaction aborts. Migrations should handle columns.


def _now_update_trigger(engine):
    """Ensure updated_at auto-update via trigger for Postgres. No-op if already created.
    Safe to attempt; if fails (e.g., not Postgres), we just ignore and update explicitly in code.
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
                        CREATE OR REPLACE FUNCTION update_updated_at_column()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            NEW.updated_at = NOW();
                            RETURN NEW;
                        END;
                        $$ language 'plpgsql';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_trigger WHERE tgname = 'set_reports_updated_at'
                    ) THEN
                        CREATE TRIGGER set_reports_updated_at
                        BEFORE UPDATE ON reports
                        FOR EACH ROW
                        EXECUTE FUNCTION update_updated_at_column();
                    END IF;
                END$$;
                """
            ))
    except Exception as e:
        # Likely running on SQLite/dev or missing perms; we will manage updated_at in code
        logger.info(f"reports: skipping trigger setup ({e})")


def _parse_paging_args():
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get('page_size', 20))
    except (TypeError, ValueError):
        page_size = 20
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    return page, page_size


def _normalize_status(raw):
    if not raw:
        return 'all'
    s = str(raw).lower()
    return s if s in {'all', 'pending', 'reviewing', 'resolved', 'escalated'} else 'all'


def _normalize_status_message_type(raw):
    if not raw:
        return None
    s = str(raw).strip().lower()
    return s if s in {'good', 'bad', 'bronze_action', 'silver_action', 'gold_action'} else None


def _normalize_username_policy(username):
    return (str(username or '').strip()).lower()


def _ensure_user_moderation_tables(engine):
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS user_moderation_state (
                user_id INTEGER PRIMARY KEY,
                require_username_change BOOLEAN NOT NULL DEFAULT FALSE,
                restricted_until TIMESTAMPTZ NULL,
                suspended_permanent BOOLEAN NOT NULL DEFAULT FALSE,
                suspended_until TIMESTAMPTZ NULL,
                reason TEXT NULL,
                updated_by INTEGER NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS username_blocklist (
                id SERIAL PRIMARY KEY,
                username_normalized VARCHAR(80) NOT NULL UNIQUE,
                reason TEXT NULL,
                created_by INTEGER NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_username_blocklist_active ON username_blocklist (is_active);"))


def _parse_iso_datetime_utc(value):
    if value in (None, ''):
        return None
    try:
        raw = str(value).strip()
        if raw.endswith('Z'):
            raw = raw.replace('Z', '+00:00')
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _ensure_report_policy_tables(engine):
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS report_safeguard_cooldown (
                id SERIAL PRIMARY KEY,
                target_type VARCHAR(16) NOT NULL,
                target_id INTEGER NOT NULL,
                scope VARCHAR(64) NOT NULL,
                safe_until TIMESTAMPTZ NOT NULL,
                source_report_id INTEGER NOT NULL UNIQUE,
                created_by INTEGER NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_report_safeguard_target_scope ON report_safeguard_cooldown (target_type, target_id, scope);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_report_safeguard_safe_until ON report_safeguard_cooldown (safe_until);"))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS timeline_warning_state (
                timeline_id INTEGER PRIMARY KEY,
                warning_scope VARCHAR(32) NOT NULL DEFAULT 'other',
                warning_reason_public TEXT NOT NULL,
                mask_content BOOLEAN NOT NULL DEFAULT TRUE,
                warning_until TIMESTAMPTZ NOT NULL,
                source_report_id INTEGER NOT NULL UNIQUE,
                updated_by INTEGER NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS timeline_ban_state (
                timeline_id INTEGER PRIMARY KEY,
                ban_reason_public TEXT NOT NULL,
                source_report_id INTEGER NOT NULL UNIQUE,
                updated_by INTEGER NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                banned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ))

        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS timeline_name_blocklist (
                id SERIAL PRIMARY KEY,
                timeline_name_normalized VARCHAR(120) NOT NULL UNIQUE,
                reason TEXT NULL,
                source_report_id INTEGER NULL,
                created_by INTEGER NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_timeline_name_blocklist_active ON timeline_name_blocklist (is_active);"))


def _ensure_broken_event_queue_table(engine):
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS broken_event_queue (
                id SERIAL PRIMARY KEY,
                event_id INTEGER NOT NULL UNIQUE,
                note TEXT NULL,
                added_by INTEGER NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_broken_event_queue_event_id ON broken_event_queue (event_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_broken_event_queue_updated_at ON broken_event_queue (updated_at DESC);"))


def _parse_safeguard_until(data, allow_custom):
    safe_until = None
    if allow_custom:
        safe_until = _parse_iso_datetime_utc(data.get('safe_until'))
        if safe_until is not None:
            if safe_until <= datetime.now(timezone.utc):
                return None, 'safe_until must be in the future'
            return safe_until, None

    days = data.get('safeguard_days', 7)
    try:
        days = int(days)
    except Exception:
        return None, 'safeguard_days must be an integer'
    if days not in {3, 7, 10}:
        return None, 'safeguard_days must be one of: 3, 7, 10'
    return datetime.now(timezone.utc) + timedelta(days=days), None


def _normalize_warning_scope(raw_scope):
    scope = str(raw_scope or '').strip().lower()
    if scope in {'general', 'timeline_profile', 'other'}:
        return 'general'
    if scope in {'action_cards', 'quote_card'}:
        return 'action_cards'
    return 'general'


def _parse_warning_until(data, allow_custom):
    if bool(data.get('warning_indef')):
        return datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc), None

    if allow_custom:
        custom_until = _parse_iso_datetime_utc(data.get('warning_until'))
        if custom_until is not None:
            if custom_until <= datetime.now(timezone.utc):
                return None, 'warning_until must be in the future'
            return custom_until, None

    days = data.get('warning_days', 7)
    try:
        days = int(days)
    except Exception:
        return None, 'warning_days must be an integer'
    if days not in {3, 7, 10}:
        return None, 'warning_days must be one of: 3, 7, 10'
    return datetime.now(timezone.utc) + timedelta(days=days), None


def _get_active_safeguard_lock(conn, target_type, target_id, scopes):
    if target_id in (None, ''):
        return None
    scope_list = [str(s) for s in (scopes or []) if s]
    if not scope_list:
        return None
    row = conn.execute(text(
        """
        SELECT scope, safe_until
        FROM report_safeguard_cooldown
        WHERE target_type = :target_type
          AND target_id = :target_id
          AND scope = ANY(:scopes)
          AND is_active = TRUE
          AND safe_until > NOW()
        ORDER BY safe_until DESC
        LIMIT 1
        """
    ), {
        'target_type': str(target_type),
        'target_id': int(target_id),
        'scopes': scope_list,
    }).mappings().first()
    if not row:
        return None
    return {
        'scope': row.get('scope'),
        'safe_until': row.get('safe_until')
    }


def _normalize_timeline_name_policy(name):
    return (str(name or '').strip()).lower()


def _get_user_moderation_state(conn, user_id):
    if not user_id:
        return {
            'require_username_change': False,
            'is_restricted': False,
            'restricted_until': None,
            'is_suspended': False,
        }

    row = conn.execute(text(
        """
        SELECT require_username_change,
               restricted_until,
               suspended_permanent,
               suspended_until,
               (restricted_until IS NOT NULL AND restricted_until > NOW()) AS is_restricted,
               (suspended_permanent OR (suspended_until IS NOT NULL AND suspended_until > NOW())) AS is_suspended
        FROM user_moderation_state
        WHERE user_id = :uid
        """
    ), {'uid': int(user_id)}).mappings().first()

    if not row:
        return {
            'require_username_change': False,
            'is_restricted': False,
            'restricted_until': None,
            'is_suspended': False,
        }

    restricted_until = row.get('restricted_until')
    return {
        'require_username_change': bool(row.get('require_username_change')),
        'is_restricted': bool(row.get('is_restricted')),
        'restricted_until': restricted_until.isoformat() if hasattr(restricted_until, 'isoformat') else None,
        'is_suspended': bool(row.get('is_suspended')),
    }


def _get_report_submission_restriction(conn, user_id):
    state = _get_user_moderation_state(conn, user_id)
    if state['is_suspended']:
        return 'Account is not permitted to submit reports.'
    if state['require_username_change']:
        return 'Username update required before submitting reports.'
    if state['is_restricted']:
        until = state.get('restricted_until')
        return f"Account is temporarily restricted until {until}." if until else 'Account is temporarily restricted.'
    return None


def _get_open_report_id(conn, where_clause, params):
    row = conn.execute(text(
        f"""
        SELECT id
        FROM reports
        WHERE status IN ('pending', 'reviewing', 'escalated')
          AND {where_clause}
        LIMIT 1
        """
    ), params).mappings().first()
    return row.get('id') if row else None


def _get_site_admin_role(conn, user_id):
    try:
        reg = conn.execute(text("SELECT to_regclass('public.site_admin')")).first()
        if not (reg and reg[0]):
            return None
        row = conn.execute(
            text('SELECT role FROM site_admin WHERE user_id = :uid'),
            {'uid': user_id}
        ).mappings().first()
        return row['role'] if row and row.get('role') else None
    except Exception as e:
        logger.info(f"reports: site_admin lookup failed ({e})")
        return None


def _require_site_admin(conn, user_id):
    role = _get_site_admin_role(conn, user_id)
    if role in {'SiteOwner', 'SiteAdmin'}:
        return True, role
    return False, None


def _is_site_protected_user(conn, user_id):
    try:
        uid = int(user_id)
    except Exception:
        return False, None

    if uid == 1:
        return True, 'SiteOwner'

    role = _get_site_admin_role(conn, uid)
    if role in {'SiteOwner', 'SiteAdmin'}:
        return True, role
    return False, None


@reports_bp.route('/timelines/<int:timeline_id>/reports', methods=['GET'])
@jwt_required()
def list_reports(timeline_id):
    """
    Placeholder: List reported posts for a timeline.
    - No DB reads yet; returns an empty, well-structured payload.
    - Enforces that caller is at least a moderator for the timeline.
    """
    # Access: moderator or higher
    timeline_row, membership_row, has_access = check_timeline_access(timeline_id, required_role='moderator')
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    status = _normalize_status(request.args.get('status'))
    page, page_size = _parse_paging_args()

    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_report_policy_tables(engine)
    _ensure_user_moderation_tables(engine)

    where_clause = "WHERE timeline_id = :timeline_id AND status <> 'escalated' AND COALESCE(report_type, 'post') = 'post'"
    params = { 'timeline_id': timeline_id }
    if status != 'all':
        where_clause += " AND status = :status"
        params['status'] = status

    # Counts per status
    with engine.begin() as conn:
        counts = {}
        for st in ['pending', 'reviewing', 'resolved']:
            res = conn.execute(text(
                """
                SELECT COUNT(*) FROM reports
                WHERE timeline_id = :tid AND status = :st AND status <> 'escalated'
                """
            ), {'tid': timeline_id, 'st': st}).scalar() or 0
            counts[st] = int(res)
        total_all = conn.execute(text(
            """
            SELECT COUNT(*) FROM reports
            WHERE timeline_id = :tid AND status <> 'escalated'
            """
        ), {'tid': timeline_id}).scalar() or 0

        # Pagination
        offset = (page - 1) * page_size
        # Include reporter username and avatar via LEFT JOIN to user table (non-breaking)
        items = conn.execute(text(
            f"""
            SELECT r.id,
                   r.timeline_id,
                   r.event_id,
                   r.report_type,
                   r.reported_user_id,
                   r.reported_timeline_id,
                   r.reporter_id,
                   r.reason,
                   r.status,
                   r.assigned_to,
                   r.resolution,
                   r.verdict,
                   r.escalation_type,
                   r.escalation_summary,
                   r.escalated_by,
                   r.escalated_at,
                   r.created_at,
                   r.updated_at,
                   r.resolved_at,
                   rsc.safe_until AS safeguard_safe_until,
                   tws.warning_scope,
                   tws.mask_content AS warning_mask_content,
                   tws.warning_until,
                   tws.is_active AS warning_is_active,
                   u.username AS reporter_username,
                   u.avatar_url AS reporter_avatar_url,
                   a.username AS assigned_to_username,
                   a.avatar_url AS assigned_to_avatar_url
            FROM reports r
            LEFT JOIN report_safeguard_cooldown rsc ON rsc.source_report_id = r.id
            LEFT JOIN timeline_warning_state tws ON tws.source_report_id = r.id
            LEFT JOIN "user" u ON u.id = r.reporter_id
            LEFT JOIN "user" a ON a.id = r.assigned_to
            {where_clause.replace('WHERE', 'WHERE')}
            ORDER BY r.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ), { **params, 'limit': page_size, 'offset': offset }).mappings().all()

    # Shape payload
    payload_items = []
    for r in items:
        payload_items.append({
            'id': r['id'],
            'timeline_id': r['timeline_id'],
            'event_id': r['event_id'],
            'reporter_id': r['reporter_id'],
            'reporter_username': r.get('reporter_username'),
            'reporter_avatar_url': r.get('reporter_avatar_url'),
            'reason': r['reason'] or '',
            'status': r['status'],
            'assigned_to': r['assigned_to'],
            'assigned_to_username': r.get('assigned_to_username'),
            'assigned_to_avatar_url': r.get('assigned_to_avatar_url'),
            'resolution': r['resolution'],
            'verdict': r['verdict'],
            'escalation_type': r.get('escalation_type'),
            'escalation_summary': r.get('escalation_summary'),
            'escalated_by': r.get('escalated_by'),
            'escalated_at': (r['escalated_at'].isoformat() if r.get('escalated_at') and hasattr(r['escalated_at'], 'isoformat') else (r.get('escalated_at') and str(r['escalated_at']) or None)),
            'reported_at': (r['created_at'].isoformat() if hasattr(r['created_at'], 'isoformat') else str(r['created_at'])),
            'updated_at': (r['updated_at'].isoformat() if hasattr(r['updated_at'], 'isoformat') else str(r['updated_at'])),
            'resolved_at': (r['resolved_at'].isoformat() if r['resolved_at'] and hasattr(r['resolved_at'], 'isoformat') else (r['resolved_at'] and str(r['resolved_at']) or None)),
            # Optional extras for UI
            'event_type': None,
        })

    data = {
        'items': payload_items,
        'status': status,
        'page': page,
        'page_size': page_size,
        'total': total_all if status == 'all' else counts.get(status, 0),
        'counts': {
            'all': total_all,
            'pending': counts.get('pending', 0),
            'reviewing': counts.get('reviewing', 0),
            'resolved': counts.get('resolved', 0),
        },
        'sort': {
            'field': 'reported_at',
            'direction': 'desc'
        }
    }
    return jsonify(data), 200


@reports_bp.route('/admins/site', methods=['GET'])
@jwt_required()
def list_site_admins():
    """
    List SiteOwner and SiteAdmin users.
    """
    engine = get_db_engine()
    with engine.begin() as conn:
        has_access, _role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403

        reg = conn.execute(text("SELECT to_regclass('public.site_admin')")).first()
        if not (reg and reg[0]):
            return jsonify({'items': []}), 200

        rows = conn.execute(text(
            """
            SELECT sa.user_id,
                   sa.role,
                   sa.created_at,
                   u.username,
                   u.email,
                   u.avatar_url
            FROM site_admin sa
            LEFT JOIN "user" u ON u.id = sa.user_id
            ORDER BY CASE WHEN sa.role = 'SiteOwner' THEN 0 ELSE 1 END, sa.created_at ASC
            """
        )).mappings().all()

    items = []
    for r in rows:
        items.append({
            'user_id': r['user_id'],
            'role': r.get('role'),
            'created_at': (r['created_at'].isoformat() if r.get('created_at') and hasattr(r['created_at'], 'isoformat') else (r.get('created_at') and str(r['created_at']) or None)),
            'username': r.get('username'),
            'email': r.get('email'),
            'avatar_url': r.get('avatar_url'),
        })

    return jsonify({'items': items}), 200


@reports_bp.route('/admins/site', methods=['POST'])
@jwt_required()
def add_site_admin():
    """Add a SiteAdmin (SiteOwner only)."""
    data = request.get_json(silent=True) or {}
    identifier = str(data.get('identifier') or data.get('user_id') or '').strip()
    if not identifier:
        return jsonify({'error': 'User identifier is required'}), 400

    engine = get_db_engine()
    with engine.begin() as conn:
        role = _get_site_admin_role(conn, get_jwt_identity())
        if role != 'SiteOwner' and int(get_jwt_identity()) != 1:
            return jsonify({'error': 'Access denied'}), 403

        reg = conn.execute(text("SELECT to_regclass('public.site_admin')")).first()
        if not (reg and reg[0]):
            return jsonify({'error': 'site_admin table missing'}), 400

        user_row = None
        if identifier.isdigit():
            user_row = conn.execute(
                text('SELECT id, username, email, avatar_url FROM "user" WHERE id = :uid'),
                {'uid': int(identifier)}
            ).mappings().first()
        else:
            user_row = conn.execute(
                text('SELECT id, username, email, avatar_url FROM "user" WHERE LOWER(username) = LOWER(:ident) OR LOWER(email) = LOWER(:ident)'),
                {'ident': identifier}
            ).mappings().first()

        if not user_row:
            return jsonify({'error': 'User not found'}), 404

        existing = conn.execute(
            text('SELECT role FROM site_admin WHERE user_id = :uid'),
            {'uid': user_row['id']}
        ).mappings().first()

        if existing:
            return jsonify({'error': 'User is already a site admin'}), 400

        conn.execute(
            text('INSERT INTO site_admin (user_id, role, created_at) VALUES (:uid, :role, NOW())'),
            {'uid': user_row['id'], 'role': 'SiteAdmin'}
        )

        return jsonify({
            'user_id': user_row['id'],
            'role': 'SiteAdmin',
            'username': user_row['username'],
            'email': user_row['email'],
            'avatar_url': user_row['avatar_url'],
        }), 201


@reports_bp.route('/admins/site/<int:user_id>', methods=['DELETE'])
@jwt_required()
def remove_site_admin(user_id):
    """Remove a SiteAdmin (SiteOwner only)."""
    if int(user_id) == 1:
        return jsonify({'error': 'Cannot remove SiteOwner'}), 403

    engine = get_db_engine()
    with engine.begin() as conn:
        role = _get_site_admin_role(conn, get_jwt_identity())
        if role != 'SiteOwner' and int(get_jwt_identity()) != 1:
            return jsonify({'error': 'Access denied'}), 403

        existing = conn.execute(
            text('SELECT role FROM site_admin WHERE user_id = :uid'),
            {'uid': user_id}
        ).mappings().first()

        if not existing:
            return jsonify({'error': 'Site admin not found'}), 404

        if existing.get('role') == 'SiteOwner':
            return jsonify({'error': 'Cannot remove SiteOwner'}), 403

        conn.execute(
            text('DELETE FROM site_admin WHERE user_id = :uid'),
            {'uid': user_id}
        )

    return jsonify({'status': 'removed'}), 200


@reports_bp.route('/reports/broken-events', methods=['GET'])
@jwt_required()
def list_broken_events_queue():
    engine = get_db_engine()
    _ensure_broken_event_queue_table(engine)

    with engine.begin() as conn:
        has_access, role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403

        rows = conn.execute(text(
            """
            SELECT q.id,
                   q.event_id,
                   q.note,
                   q.added_by,
                   q.created_at,
                   q.updated_at,
                   adder.username AS added_by_username,
                   (e.id IS NOT NULL) AS event_exists,
                   e.timeline_id,
                   e.title AS event_title,
                   e.type AS event_type,
                   e.created_by AS event_created_by,
                   e.created_at AS event_created_at,
                   creator.username AS event_creator_username,
                   t.name AS timeline_name,
                   t.timeline_type,
                   t.visibility AS timeline_visibility
            FROM broken_event_queue q
            LEFT JOIN event e ON e.id = q.event_id
            LEFT JOIN timeline t ON t.id = e.timeline_id
            LEFT JOIN "user" creator ON creator.id = e.created_by
            LEFT JOIN "user" adder ON adder.id = q.added_by
            ORDER BY q.updated_at DESC, q.id DESC
            """
        )).mappings().all()

    items = []
    for row in rows:
        items.append({
            'id': int(row.get('id')),
            'event_id': int(row.get('event_id')),
            'note': row.get('note') or '',
            'added_by': row.get('added_by'),
            'added_by_username': row.get('added_by_username') or '',
            'created_at': row.get('created_at').isoformat() if hasattr(row.get('created_at'), 'isoformat') else None,
            'updated_at': row.get('updated_at').isoformat() if hasattr(row.get('updated_at'), 'isoformat') else None,
            'event_exists': bool(row.get('event_exists')),
            'timeline_id': row.get('timeline_id'),
            'timeline_name': row.get('timeline_name') or '',
            'timeline_type': row.get('timeline_type') or '',
            'timeline_visibility': row.get('timeline_visibility') or '',
            'event_title': row.get('event_title') or '',
            'event_type': row.get('event_type') or '',
            'event_created_by': row.get('event_created_by'),
            'event_creator_username': row.get('event_creator_username') or '',
            'event_created_at': row.get('event_created_at').isoformat() if hasattr(row.get('event_created_at'), 'isoformat') else None,
        })

    return jsonify({'items': items}), 200


@reports_bp.route('/reports/broken-events', methods=['POST'])
@jwt_required()
def add_broken_event_queue_item():
    data = request.get_json(silent=True) or {}
    try:
        event_id = int(data.get('event_id'))
    except Exception:
        return jsonify({'error': 'event_id must be an integer'}), 400

    if event_id <= 0:
        return jsonify({'error': 'event_id must be positive'}), 400

    note = str(data.get('note') or '').strip()
    actor_id = int(get_jwt_identity())
    is_home_auto_report = 'source=home_auto' in note.lower()

    engine = get_db_engine()
    _ensure_broken_event_queue_table(engine)

    with engine.begin() as conn:
        event_exists = bool(conn.execute(text(
            "SELECT 1 FROM event WHERE id = :event_id LIMIT 1"
        ), {'event_id': event_id}).first())

        # Ignore stale Home auto-reports for events that are already gone
        # (for example, intentionally deleted during triage).
        if is_home_auto_report and not event_exists:
            return jsonify({
                'message': 'Ignored stale home auto-report for missing event',
                'ignored': True,
                'event_id': event_id,
            }), 200

        row = conn.execute(text(
            """
            INSERT INTO broken_event_queue (event_id, note, added_by, created_at, updated_at)
            VALUES (:event_id, :note, :added_by, NOW(), NOW())
            ON CONFLICT (event_id)
            DO UPDATE SET note = EXCLUDED.note,
                          added_by = EXCLUDED.added_by,
                          updated_at = NOW()
            RETURNING id, event_id
            """
        ), {
            'event_id': event_id,
            'note': note or None,
            'added_by': actor_id,
        }).mappings().first()

    return jsonify({
        'message': 'Broken event queued',
        'item': {
            'id': int(row['id']),
            'event_id': int(row['event_id']),
        },
    }), 200


@reports_bp.route('/reports/broken-events/<int:queue_id>', methods=['DELETE'])
@jwt_required()
def remove_broken_event_queue_item(queue_id):
    engine = get_db_engine()
    _ensure_broken_event_queue_table(engine)

    with engine.begin() as conn:
        has_access, role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403

        deleted = conn.execute(text(
            """
            DELETE FROM broken_event_queue
            WHERE id = :queue_id
            RETURNING id, event_id
            """
        ), {'queue_id': int(queue_id)}).mappings().first()

        if not deleted:
            return jsonify({'error': 'Queue item not found'}), 404

    return jsonify({
        'message': 'Broken event queue item removed',
        'id': int(deleted['id']),
        'event_id': int(deleted['event_id']),
    }), 200


@reports_bp.route('/reports/broken-events/<int:event_id>/delete', methods=['POST'])
@jwt_required()
def delete_broken_event_by_id(event_id):
    data = request.get_json(silent=True) or {}
    remove_from_queue = bool(data.get('remove_from_queue', True))

    engine = get_db_engine()
    _ensure_broken_event_queue_table(engine)

    with engine.begin() as conn:
        has_access, role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403

        event_row = conn.execute(text(
            """
            SELECT id, timeline_id, media_url, cloudinary_id
            FROM event
            WHERE id = :event_id
            """
        ), {'event_id': int(event_id)}).mappings().first()

        if not event_row:
            queue_deleted_count = 0
            if remove_from_queue:
                queue_deleted_count = int(conn.execute(text(
                    "DELETE FROM broken_event_queue WHERE event_id = :event_id"
                ), {'event_id': int(event_id)}).rowcount or 0)

            return jsonify({
                'error': 'Event not found',
                'event_id': int(event_id),
                'queue_deleted_count': queue_deleted_count,
            }), 404

        media_deleted = False
        media_url = str(event_row.get('media_url') or '').strip()
        cloudinary_id = str(event_row.get('cloudinary_id') or '').strip()
        public_id = cloudinary_id

        if not public_id and media_url and ('cloudinary.com' in media_url or 'res.cloudinary' in media_url):
            try:
                parts = media_url.split('/')
                if 'upload' in parts:
                    upload_index = parts.index('upload')
                    if upload_index + 2 < len(parts):
                        if parts[upload_index + 1].startswith('v'):
                            public_id = '/'.join(parts[upload_index + 2:])
                        else:
                            public_id = '/'.join(parts[upload_index + 1:])
            except Exception:
                public_id = ''

        if public_id:
            try:
                from cloud_storage import delete_file
                delete_result = delete_file(public_id)
                media_deleted = bool(delete_result.get('success'))
            except Exception:
                media_deleted = False

        conn.execute(text("DELETE FROM vote WHERE event_id = :event_id"), {'event_id': int(event_id)})
        conn.execute(text("DELETE FROM event_timeline_association WHERE event_id = :event_id"), {'event_id': int(event_id)})
        conn.execute(text("DELETE FROM event_timeline_refs WHERE event_id = :event_id"), {'event_id': int(event_id)})
        conn.execute(text("DELETE FROM event_tags WHERE event_id = :event_id"), {'event_id': int(event_id)})
        conn.execute(text("DELETE FROM timeline_block_list WHERE event_id = :event_id"), {'event_id': int(event_id)})
        conn.execute(text("DELETE FROM reports WHERE event_id = :event_id"), {'event_id': int(event_id)})

        deleted_count = int(conn.execute(text(
            "DELETE FROM event WHERE id = :event_id"
        ), {'event_id': int(event_id)}).rowcount or 0)

        queue_deleted_count = 0
        queue_updated_count = 0
        if remove_from_queue:
            queue_deleted_count = int(conn.execute(text(
                "DELETE FROM broken_event_queue WHERE event_id = :event_id"
            ), {'event_id': int(event_id)}).rowcount or 0)
        else:
            deleted_marker = f"resolution=deleted_by_admin | deleted_at={datetime.now(timezone.utc).isoformat()}"
            queue_updated_count = int(conn.execute(text(
                """
                UPDATE broken_event_queue
                SET note = CASE
                    WHEN note IS NULL OR BTRIM(note) = '' THEN :marker
                    WHEN POSITION('resolution=deleted_by_admin' IN LOWER(note)) > 0 THEN note
                    ELSE note || ' | ' || :marker
                END,
                updated_at = NOW()
                WHERE event_id = :event_id
                """
            ), {
                'event_id': int(event_id),
                'marker': deleted_marker,
            }).rowcount or 0)

    if deleted_count <= 0:
        return jsonify({'error': 'Event delete failed'}), 500

    return jsonify({
        'message': 'Event deleted from broken-event queue flow',
        'event_id': int(event_id),
        'timeline_id': int(event_row.get('timeline_id') or 0),
        'deleted_count': deleted_count,
        'queue_deleted_count': queue_deleted_count,
        'queue_updated_count': queue_updated_count,
        'media_deleted': media_deleted,
    }), 200


@reports_bp.route('/reports', methods=['GET'])
@jwt_required()
def list_site_reports():
    """
    List reported items across all timelines (SiteOwner/SiteAdmin only).
    """
    status = _normalize_status(request.args.get('status'))
    report_type = str(request.args.get('report_type') or 'all').strip().lower()
    if report_type not in {'all', 'post', 'user', 'timeline'}:
        report_type = 'all'
    page, page_size = _parse_paging_args()

    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_report_policy_tables(engine)

    with engine.begin() as conn:
        has_access, _role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403

        escalation_filter = "(r.escalated_at IS NOT NULL OR r.escalation_type IS NOT NULL)"
        escalation_filter_counts = "(escalated_at IS NOT NULL OR escalation_type IS NOT NULL)"
        site_scope_filter = f"({escalation_filter} OR t.timeline_type = 'hashtag' OR COALESCE(r.report_type, 'post') <> 'post')"
        site_scope_filter_counts = (
            f"({escalation_filter_counts} OR COALESCE(report_type, 'post') <> 'post' OR timeline_id IN "
            "(SELECT id FROM timeline WHERE timeline_type = 'hashtag'))"
        )
        where_clause = (
            "WHERE r.status IN ('pending', 'escalated', 'reviewing', 'resolved') "
            f"AND {site_scope_filter}"
        )
        counts_type_clause = ''
        params = {}
        count_params = {}
        if report_type != 'all':
            where_clause += " AND COALESCE(r.report_type, 'post') = :report_type"
            counts_type_clause = " AND COALESCE(report_type, 'post') = :report_type"
            params['report_type'] = report_type
            count_params['report_type'] = report_type

        if status != 'all':
            if status == 'pending':
                where_clause = (
                    "WHERE r.status IN ('pending', 'escalated') "
                    f"AND {site_scope_filter}"
                )
                if report_type != 'all':
                    where_clause += " AND COALESCE(r.report_type, 'post') = :report_type"
            else:
                where_clause = f"WHERE r.status = :status AND {site_scope_filter}"
                params['status'] = status
                if report_type != 'all':
                    where_clause += " AND COALESCE(r.report_type, 'post') = :report_type"

        counts = {}
        counts = {
            'pending': int(conn.execute(text(
                f"SELECT COUNT(*) FROM reports WHERE status IN ('pending', 'escalated') AND {site_scope_filter_counts}{counts_type_clause}"
            ), count_params).scalar() or 0),
            'reviewing': int(conn.execute(text(
                f"SELECT COUNT(*) FROM reports WHERE status = 'reviewing' AND {site_scope_filter_counts}{counts_type_clause}"
            ), count_params).scalar() or 0),
            'resolved': int(conn.execute(text(
                f"SELECT COUNT(*) FROM reports WHERE status = 'resolved' AND {site_scope_filter_counts}{counts_type_clause}"
            ), count_params).scalar() or 0),
        }
        total_all = sum(counts.values())

        offset = (page - 1) * page_size
        items = conn.execute(text(
            f"""
            SELECT r.id,
                   r.timeline_id,
                   r.event_id,
                   r.report_type,
                   r.reported_user_id,
                   r.reported_timeline_id,
                   r.reporter_id,
                   r.reason,
                   r.status,
                   r.assigned_to,
                   r.resolution,
                   r.verdict,
                   r.escalation_type,
                   r.escalation_summary,
                   r.escalated_by,
                   r.escalated_at,
                   r.created_at,
                   r.updated_at,
                   r.resolved_at,
                   rsc.safe_until AS safeguard_safe_until,
                   tws.warning_scope,
                   tws.mask_content AS warning_mask_content,
                   tws.warning_until,
                   tws.is_active AS warning_is_active,
                   u.username AS reporter_username,
                   u.avatar_url AS reporter_avatar_url,
                   a.username AS assigned_to_username,
                   a.avatar_url AS assigned_to_avatar_url,
                   ru.username AS reported_user_username,
                   ru.avatar_url AS reported_user_avatar_url,
                   t.name AS timeline_name,
                   t.timeline_type,
                   rt.name AS reported_timeline_name,
                   rt.timeline_type AS reported_timeline_type
            FROM reports r
            LEFT JOIN report_safeguard_cooldown rsc ON rsc.source_report_id = r.id
            LEFT JOIN timeline_warning_state tws ON tws.source_report_id = r.id
            LEFT JOIN "user" u ON u.id = r.reporter_id
            LEFT JOIN "user" a ON a.id = r.assigned_to
            LEFT JOIN "user" ru ON ru.id = r.reported_user_id
            LEFT JOIN timeline t ON t.id = r.timeline_id
            LEFT JOIN timeline rt ON rt.id = r.reported_timeline_id
            {where_clause}
            ORDER BY r.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ), { **params, 'limit': page_size, 'offset': offset }).mappings().all()

    payload_items = []
    for r in items:
        payload_items.append({
            'id': r['id'],
            'timeline_id': r['timeline_id'],
            'timeline_name': r.get('timeline_name'),
            'timeline_type': r.get('timeline_type'),
            'event_id': r['event_id'],
            'report_type': r.get('report_type') or 'post',
            'reported_user_id': r.get('reported_user_id'),
            'reported_user_username': r.get('reported_user_username'),
            'reported_user_avatar_url': r.get('reported_user_avatar_url'),
            'reported_timeline_id': r.get('reported_timeline_id'),
            'reported_timeline_name': r.get('reported_timeline_name'),
            'reported_timeline_type': r.get('reported_timeline_type'),
            'reporter_id': r['reporter_id'],
            'reporter_username': r.get('reporter_username'),
            'reporter_avatar_url': r.get('reporter_avatar_url'),
            'reason': r['reason'] or '',
            'status': r['status'],
            'assigned_to': r['assigned_to'],
            'assigned_to_username': r.get('assigned_to_username'),
            'assigned_to_avatar_url': r.get('assigned_to_avatar_url'),
            'resolution': r['resolution'],
            'verdict': r['verdict'],
            'escalation_type': r.get('escalation_type'),
            'escalation_summary': r.get('escalation_summary'),
            'escalated_by': r.get('escalated_by'),
            'escalated_at': (r['escalated_at'].isoformat() if r.get('escalated_at') and hasattr(r['escalated_at'], 'isoformat') else (r.get('escalated_at') and str(r['escalated_at']) or None)),
            'reported_at': (r['created_at'].isoformat() if hasattr(r['created_at'], 'isoformat') else str(r['created_at'])),
            'updated_at': (r['updated_at'].isoformat() if hasattr(r['updated_at'], 'isoformat') else str(r['updated_at'])),
            'resolved_at': (r['resolved_at'].isoformat() if r['resolved_at'] and hasattr(r['resolved_at'], 'isoformat') else (r['resolved_at'] and str(r['resolved_at']) or None)),
            'safeguard_safe_until': (r['safeguard_safe_until'].isoformat() if r.get('safeguard_safe_until') and hasattr(r['safeguard_safe_until'], 'isoformat') else (r.get('safeguard_safe_until') and str(r['safeguard_safe_until']) or None)),
            'warning_scope': r.get('warning_scope'),
            'warning_mask_content': bool(r.get('warning_mask_content')) if r.get('warning_mask_content') is not None else None,
            'warning_until': (r['warning_until'].isoformat() if r.get('warning_until') and hasattr(r['warning_until'], 'isoformat') else (r.get('warning_until') and str(r['warning_until']) or None)),
            'warning_is_active': bool(r.get('warning_is_active')) if r.get('warning_is_active') is not None else None,
            'event_type': None,
        })

    data = {
        'items': payload_items,
        'status': status,
        'page': page,
        'page_size': page_size,
        'total': total_all if status == 'all' else counts.get(status, 0),
        'counts': {
            'all': total_all,
            'pending': counts.get('pending', 0),
            'reviewing': counts.get('reviewing', 0),
            'resolved': counts.get('resolved', 0),
        },
        'sort': {
            'field': 'reported_at',
            'direction': 'desc'
        }
    }
    return jsonify(data), 200


@reports_bp.route('/reports/<int:report_id>/accept', methods=['POST'])
@jwt_required()
def accept_site_report(report_id):
    """
    Accept a report for review (SiteOwner/SiteAdmin only).
    """
    engine = get_db_engine()
    _ensure_reports_table(engine)

    with engine.begin() as conn:
        has_access, _role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403

        actor_id = get_user_id()
        res = conn.execute(text(
            """
            UPDATE reports
            SET status = 'reviewing', assigned_to = :actor, updated_at = NOW()
            WHERE id = :rid
            RETURNING id, status, assigned_to, updated_at, timeline_id
            """
        ), {'actor': actor_id, 'rid': report_id}).mappings().first()
        if not res:
            return jsonify({'error': 'Report not found'}), 404

    return jsonify({
        'message': 'Accepted for review',
        'report_id': res['id'],
        'timeline_id': res['timeline_id'],
        'assigned_to': res['assigned_to'],
        'new_status': res['status'],
        'timestamp': (res['updated_at'].isoformat() if hasattr(res['updated_at'], 'isoformat') else str(res['updated_at']))
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/reports/<int:report_id>/escalate', methods=['POST'])
@jwt_required()
def escalate_report(timeline_id, report_id):
    """
    Escalate a report to Site Control.
    Body: { escalation_type: 'edit'|'delete', summary?: string }
    """
    timeline_row, membership_row, has_access = check_timeline_access(timeline_id, required_role='moderator')
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    escalation_type = str(data.get('escalation_type', '')).lower().strip()
    if escalation_type not in {'edit', 'delete'}:
        return jsonify({'error': 'Invalid escalation_type'}), 400
    summary = (data.get('summary') or '').strip()

    actor_id = get_user_id()
    engine = get_db_engine()
    _ensure_reports_table(engine)

    with engine.begin() as conn:
        res = conn.execute(text(
            """
            UPDATE reports
            SET status = 'escalated',
                escalation_type = :esc_type,
                escalation_summary = :summary,
                escalated_by = :actor,
                escalated_at = NOW(),
                assigned_to = NULL,
                updated_at = NOW()
            WHERE id = :rid AND timeline_id = :tid
            RETURNING id, status, escalation_type, escalation_summary, escalated_at
            """
        ), {'esc_type': escalation_type, 'summary': summary, 'actor': actor_id, 'rid': report_id, 'tid': timeline_id}).mappings().first()
        if not res:
            return jsonify({'error': 'Report not found'}), 404

    return jsonify({
        'message': 'Report escalated',
        'report_id': res['id'],
        'timeline_id': timeline_id,
        'status': res['status'],
        'escalation_type': res['escalation_type'],
        'escalation_summary': res['escalation_summary'],
        'escalated_at': (res['escalated_at'].isoformat() if hasattr(res['escalated_at'], 'isoformat') else str(res['escalated_at']))
    }), 200


@reports_bp.route('/reports/<int:report_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_site_report(report_id):
    """
    Resolve a report across the site (SiteOwner/SiteAdmin only).
    """
    data = request.get_json(silent=True) or {}
    action = str(data.get('action', '')).lower()
    if action not in {'remove', 'delete', 'safeguard', 'edit', 'require_username_change', 'restrict_user', 'suspend_user', 'issue_warning', 'ban_timeline'}:
        return jsonify({'error': 'Invalid action'}), 400
    verdict = (data.get('verdict') or '').strip()
    lock_edit = bool(data.get('lock_edit'))
    if not verdict:
        return jsonify({'error': 'verdict is required'}), 400

    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_user_moderation_tables(engine)
    _ensure_report_policy_tables(engine)

    full_delete_required = False
    full_delete_reason = None
    event_id_for_report = None
    deleted_event = False
    deleted_assoc_total = None
    deleted_tags_total = None
    deleted_blocklist_total = None
    media_deleted = False
    moderation_update = None
    username_blocked = False
    safeguard_safe_until = None
    warning_until = None
    banned_timeline_id = None

    with engine.begin() as conn:
        has_access, _role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403

        rep = conn.execute(text(
            """
            SELECT event_id, timeline_id, report_type, reported_user_id, reported_timeline_id
            FROM reports
            WHERE id = :rid
            """
        ), {'rid': report_id}).mappings().first()
        if not rep:
            return jsonify({'error': 'Report not found'}), 404
        report_type = str(rep.get('report_type') or 'post').lower()
        if report_type == 'post' and action in {'require_username_change', 'restrict_user', 'suspend_user', 'issue_warning', 'ban_timeline'}:
            return jsonify({'error': f"Action '{action}' is not supported for post tickets"}), 400
        if report_type == 'user' and action in {'delete', 'remove', 'edit', 'issue_warning', 'ban_timeline'}:
            return jsonify({'error': f"Action '{action}' is not supported for user tickets"}), 400
        if report_type == 'timeline' and action in {'delete', 'remove', 'edit', 'require_username_change', 'restrict_user', 'suspend_user'}:
            return jsonify({'error': f"Action '{action}' is not supported for this ticket type"}), 400
        if report_type not in {'post', 'user', 'timeline'}:
            return jsonify({'error': 'Unsupported report type'}), 400

        event_id_for_report = int(rep['event_id']) if rep.get('event_id') is not None else None
        timeline_id = int(rep['timeline_id']) if rep.get('timeline_id') is not None else None
        reported_user_id = int(rep['reported_user_id']) if rep.get('reported_user_id') is not None else None
        reported_timeline_id = int(rep['reported_timeline_id']) if rep.get('reported_timeline_id') is not None else None

        res = conn.execute(text(
            """
            UPDATE reports
            SET status = 'resolved',
                resolution = :action,
                verdict = :verdict,
                resolved_at = NOW(),
                updated_at = NOW(),
                assigned_to = COALESCE(assigned_to, :actor)
            WHERE id = :rid
            RETURNING id, status, resolution, verdict, resolved_at, timeline_id
            """
        ), {'action': action, 'verdict': verdict, 'actor': get_user_id(), 'rid': report_id}).mappings().first()
        if not res:
            return jsonify({'error': 'Report not found'}), 404

        if event_id_for_report is not None and (action == 'edit' or (lock_edit and action in {'safeguard', 'remove'})):
            try:
                conn.execute(text(
                    """
                    UPDATE event
                    SET edit_locked = TRUE
                    WHERE id = :eid
                    """
                ), {'eid': event_id_for_report})
            except Exception:
                pass

        if action == 'safeguard':
            target_type = None
            target_id = None
            scope = 'site_global'
            if report_type == 'post' and event_id_for_report is not None:
                target_type = 'post'
                target_id = event_id_for_report
            elif report_type == 'user' and reported_user_id is not None:
                target_type = 'user'
                target_id = reported_user_id
            elif report_type == 'timeline' and (reported_timeline_id is not None or timeline_id is not None):
                target_type = 'timeline'
                target_id = reported_timeline_id if reported_timeline_id is not None else timeline_id

            if target_type is None or target_id is None:
                return jsonify({'error': 'Unable to determine safeguard target'}), 400

            parsed_until, parse_err = _parse_safeguard_until(data, allow_custom=True)
            if parse_err:
                return jsonify({'error': parse_err}), 400

            safeguard_safe_until = parsed_until
            conn.execute(text(
                """
                INSERT INTO report_safeguard_cooldown (
                    target_type,
                    target_id,
                    scope,
                    safe_until,
                    source_report_id,
                    created_by,
                    is_active
                )
                VALUES (
                    :target_type,
                    :target_id,
                    :scope,
                    :safe_until,
                    :source_report_id,
                    :created_by,
                    TRUE
                )
                ON CONFLICT (source_report_id) DO UPDATE
                SET target_type = EXCLUDED.target_type,
                    target_id = EXCLUDED.target_id,
                    scope = EXCLUDED.scope,
                    safe_until = EXCLUDED.safe_until,
                    created_by = EXCLUDED.created_by,
                    is_active = TRUE
                """
            ), {
                'target_type': target_type,
                'target_id': target_id,
                'scope': scope,
                'safe_until': safeguard_safe_until,
                'source_report_id': int(report_id),
                'created_by': get_user_id(),
            })

        if action == 'issue_warning' and report_type == 'timeline':
            target_timeline_id = reported_timeline_id if reported_timeline_id is not None else timeline_id
            if target_timeline_id is None:
                return jsonify({'error': 'Timeline ticket missing timeline target'}), 400
            warning_scope = _normalize_warning_scope(data.get('warning_scope'))
            if warning_scope == 'action_cards':
                timeline_type_row = conn.execute(text(
                    "SELECT timeline_type FROM timeline WHERE id = :tid LIMIT 1"
                ), {'tid': int(target_timeline_id)}).mappings().first()
                timeline_type = str(timeline_type_row.get('timeline_type') or '').lower() if timeline_type_row else ''
                if timeline_type != 'community':
                    warning_scope = 'general'
            mask_content = bool(data.get('mask_content', True))
            warning_until, warning_parse_err = _parse_warning_until(data, allow_custom=False)
            if warning_parse_err:
                return jsonify({'error': warning_parse_err}), 400
            conn.execute(text(
                """
                INSERT INTO timeline_warning_state (
                    timeline_id,
                    warning_scope,
                    warning_reason_public,
                    mask_content,
                    warning_until,
                    source_report_id,
                    updated_by,
                    is_active,
                    updated_at
                )
                VALUES (
                    :timeline_id,
                    :warning_scope,
                    :reason,
                    :mask_content,
                    :warning_until,
                    :source_report_id,
                    :updated_by,
                    TRUE,
                    NOW()
                )
                ON CONFLICT (timeline_id) DO UPDATE
                SET warning_scope = EXCLUDED.warning_scope,
                    warning_reason_public = EXCLUDED.warning_reason_public,
                    mask_content = EXCLUDED.mask_content,
                    warning_until = EXCLUDED.warning_until,
                    source_report_id = EXCLUDED.source_report_id,
                    updated_by = EXCLUDED.updated_by,
                    is_active = TRUE,
                    updated_at = NOW()
                """
            ), {
                'timeline_id': target_timeline_id,
                'warning_scope': warning_scope,
                'reason': verdict,
                'mask_content': mask_content,
                'warning_until': warning_until,
                'source_report_id': int(report_id),
                'updated_by': get_user_id(),
            })

        if action == 'ban_timeline' and report_type == 'timeline':
            target_timeline_id = reported_timeline_id if reported_timeline_id is not None else timeline_id
            if target_timeline_id is None:
                return jsonify({'error': 'Timeline ticket missing timeline target'}), 400
            banned_timeline_id = int(target_timeline_id)
            timeline_row = conn.execute(text(
                "SELECT name FROM timeline WHERE id = :tid LIMIT 1"
            ), {'tid': banned_timeline_id}).mappings().first()
            normalized_timeline_name = _normalize_timeline_name_policy(timeline_row.get('name') if timeline_row else '')

            conn.execute(text(
                """
                INSERT INTO timeline_ban_state (
                    timeline_id,
                    ban_reason_public,
                    source_report_id,
                    updated_by,
                    is_active,
                    banned_at,
                    updated_at
                )
                VALUES (
                    :timeline_id,
                    :reason,
                    :source_report_id,
                    :updated_by,
                    TRUE,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (timeline_id) DO UPDATE
                SET ban_reason_public = EXCLUDED.ban_reason_public,
                    source_report_id = EXCLUDED.source_report_id,
                    updated_by = EXCLUDED.updated_by,
                    is_active = TRUE,
                    updated_at = NOW()
                """
            ), {
                'timeline_id': banned_timeline_id,
                'reason': verdict,
                'source_report_id': int(report_id),
                'updated_by': get_user_id(),
            })

            if normalized_timeline_name:
                conn.execute(text(
                    """
                    INSERT INTO timeline_name_blocklist (
                        timeline_name_normalized,
                        reason,
                        source_report_id,
                        created_by,
                        is_active
                    )
                    VALUES (
                        :timeline_name_normalized,
                        :reason,
                        :source_report_id,
                        :created_by,
                        TRUE
                    )
                    ON CONFLICT (timeline_name_normalized) DO UPDATE
                    SET reason = EXCLUDED.reason,
                        source_report_id = EXCLUDED.source_report_id,
                        created_by = EXCLUDED.created_by,
                        is_active = TRUE
                    """
                ), {
                    'timeline_name_normalized': normalized_timeline_name,
                    'reason': verdict,
                    'source_report_id': int(report_id),
                    'created_by': get_user_id(),
                })

        if action == 'remove':
            from sqlalchemy import text as _sql_text
            try:
                conn.execute(_sql_text(
                    """
                    CREATE TABLE IF NOT EXISTS timeline_block_list (
                        event_id INTEGER NOT NULL,
                        timeline_id INTEGER NOT NULL,
                        removed_by INTEGER NULL,
                        removed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (event_id, timeline_id)
                    )
                    """
                ))
            except Exception:
                pass

            owner_row = conn.execute(_sql_text("SELECT timeline_id FROM event WHERE id = :eid"), { 'eid': event_id_for_report }).first()
            owner_id = int(owner_row[0]) if owner_row and owner_row[0] is not None else None
            active_ids = set()
            if owner_id:
                active_ids.add(owner_id)

            assoc_rows = conn.execute(_sql_text(
                "SELECT DISTINCT timeline_id FROM event_timeline_association WHERE event_id = :eid"
            ), { 'eid': event_id_for_report }).all()
            for r in assoc_rows:
                if r and r[0] is not None:
                    active_ids.add(int(r[0]))

            def _reg_exists(tbl: str) -> bool:
                try:
                    rr = conn.execute(_sql_text("SELECT to_regclass(:t)"), { 't': f'public.{tbl}' }).first()
                    return bool(rr and rr[0])
                except Exception:
                    return False

            tag_count = 0
            if _reg_exists('event_tags'):
                cnt = conn.execute(_sql_text("SELECT COUNT(*) FROM event_tags WHERE event_id = :eid"), { 'eid': event_id_for_report }).first()
                tag_count = int(cnt[0]) if cnt and cnt[0] is not None else 0
            elif _reg_exists('event_tag'):
                cnt = conn.execute(_sql_text("SELECT COUNT(*) FROM event_tag WHERE event_id = :eid"), { 'eid': event_id_for_report }).first()
                tag_count = int(cnt[0]) if cnt and cnt[0] is not None else 0

            tag_names = []
            if tag_count > 0:
                candidates = []
                if _reg_exists('tags') and _reg_exists('event_tags'):
                    candidates.append("SELECT t.name FROM tags t JOIN event_tags et ON et.tag_id = t.id WHERE et.event_id = :eid")
                if _reg_exists('tags') and _reg_exists('event_tag'):
                    candidates.append("SELECT t.name FROM tags t JOIN event_tag et ON et.tag_id = t.id WHERE et.event_id = :eid")
                if _reg_exists('tag') and _reg_exists('event_tags'):
                    candidates.append("SELECT t.name FROM tag t JOIN event_tags et ON et.tag_id = t.id WHERE et.event_id = :eid")
                if _reg_exists('tag') and _reg_exists('event_tag'):
                    candidates.append("SELECT t.name FROM tag t JOIN event_tag et ON et.tag_id = t.id WHERE et.event_id = :eid")
                for q in candidates:
                    rows = conn.execute(_sql_text(q), { 'eid': event_id_for_report }).all()
                    names = [str(r[0]) for r in rows if r and r[0]]
                    if names:
                        tag_names = names
                        break
            if tag_names:
                for nm in list({ n.lower() for n in tag_names if n }):
                    try:
                        tlr = conn.execute(_sql_text(
                            "SELECT id FROM timeline WHERE LOWER(name) = :name"
                        ), { 'name': nm }).first()
                        if tlr and tlr[0] is not None:
                            active_ids.add(int(tlr[0]))
                    except Exception:
                        continue

            blocked_rows = conn.execute(_sql_text(
                "SELECT timeline_id FROM timeline_block_list WHERE event_id = :eid"
            ), { 'eid': event_id_for_report }).all()
            blocked_ids = { int(r[0]) for r in blocked_rows if r and r[0] is not None }
            effective_active_ids = { i for i in active_ids if i not in blocked_ids }
            other_active_ids = { i for i in effective_active_ids if i != timeline_id }

            exists_elsewhere = (len(other_active_ids) >= 1) or (tag_count >= 2)
            if not exists_elsewhere:
                return jsonify({
                    'error': 'Removal denied: event would have no remaining placements after removal',
                    'event_id': event_id_for_report,
                    'timeline_id': timeline_id,
                    'effective_active_ids': list(sorted(effective_active_ids)),
                    'other_active_ids': list(sorted(other_active_ids)),
                    'tag_count': tag_count
                }), 409

            conn.execute(_sql_text(
                """
                INSERT INTO timeline_block_list (event_id, timeline_id, removed_by)
                VALUES (:eid, :tid, :actor)
                ON CONFLICT (event_id, timeline_id) DO NOTHING
                """
            ), { 'eid': event_id_for_report, 'tid': timeline_id, 'actor': get_jwt_identity() })

            del_res = conn.execute(_sql_text(
                """
                DELETE FROM event_timeline_association
                WHERE event_id = :eid AND timeline_id = :tid
                """
            ), { 'eid': event_id_for_report, 'tid': timeline_id })
            deleted_assoc_count = getattr(del_res, 'rowcount', None)

            blocked_ids_after = blocked_ids | { timeline_id }
            remaining_after = { i for i in active_ids if i not in blocked_ids_after }
            if len(remaining_after) == 0:
                full_delete_required = True
                full_delete_reason = 'Event is blocked on all timelines'

        elif action == 'delete':
            from sqlalchemy import text as _sql_text
            media_url = None
            cloudinary_id = None
            event_type = None
            try:
                media_row = conn.execute(_sql_text(
                    "SELECT media_url, cloudinary_id, type FROM event WHERE id = :eid"
                ), { 'eid': event_id_for_report }).first()
                if media_row:
                    media_url = media_row[0]
                    cloudinary_id = media_row[1]
                    event_type = media_row[2]
            except Exception:
                media_row = None

            def _reg_exists(tbl: str) -> bool:
                try:
                    rr = conn.execute(_sql_text("SELECT to_regclass(:t)"), { 't': f'public.{tbl}' }).first()
                    return bool(rr and rr[0])
                except Exception:
                    return False

            deleted_assoc_total = 0
            if _reg_exists('event_timeline_association'):
                try:
                    res_a = conn.execute(_sql_text(
                        "DELETE FROM event_timeline_association WHERE event_id = :eid"
                    ), { 'eid': event_id_for_report })
                    deleted_assoc_total = int(getattr(res_a, 'rowcount', 0) or 0)
                except Exception:
                    pass

        if action in {'require_username_change', 'restrict_user', 'suspend_user'} and report_type == 'user' and reported_user_id:
            actor_id = int(get_user_id()) if get_user_id() is not None else None

            if action == 'require_username_change':
                block_current_username = bool(data.get('block_current_username', True))
                conn.execute(text(
                    """
                    INSERT INTO user_moderation_state (user_id, require_username_change, reason, updated_by, updated_at)
                    VALUES (:uid, TRUE, :reason, :actor, NOW())
                    ON CONFLICT (user_id) DO UPDATE
                    SET require_username_change = TRUE,
                        reason = :reason,
                        updated_by = :actor,
                        updated_at = NOW()
                    """
                ), {'uid': reported_user_id, 'reason': verdict, 'actor': actor_id})

                if block_current_username:
                    user_row = conn.execute(text(
                        "SELECT username FROM \"user\" WHERE id = :uid"
                    ), {'uid': reported_user_id}).mappings().first()
                    username_value = (user_row.get('username') if user_row else None)
                    normalized_username = _normalize_username_policy(username_value)
                    if normalized_username:
                        conn.execute(text(
                            """
                            INSERT INTO username_blocklist (username_normalized, reason, created_by, is_active)
                            VALUES (:uname, :reason, :actor, TRUE)
                            ON CONFLICT (username_normalized) DO UPDATE
                            SET reason = EXCLUDED.reason,
                                created_by = EXCLUDED.created_by,
                                is_active = TRUE
                            """
                        ), {'uname': normalized_username, 'reason': verdict, 'actor': actor_id})
                        username_blocked = True

                moderation_update = {'action': 'require_username_change', 'user_id': reported_user_id}

            elif action == 'restrict_user':
                restriction_until = _parse_iso_datetime_utc(data.get('restriction_until'))
                if not restriction_until:
                    return jsonify({'error': 'restriction_until is required for restrict_user'}), 400
                if restriction_until <= datetime.now(timezone.utc):
                    return jsonify({'error': 'restriction_until must be in the future'}), 400

                conn.execute(text(
                    """
                    INSERT INTO user_moderation_state (user_id, restricted_until, reason, updated_by, updated_at)
                    VALUES (:uid, :until_ts, :reason, :actor, NOW())
                    ON CONFLICT (user_id) DO UPDATE
                    SET restricted_until = :until_ts,
                        reason = :reason,
                        updated_by = :actor,
                        updated_at = NOW()
                    """
                ), {'uid': reported_user_id, 'until_ts': restriction_until, 'reason': verdict, 'actor': actor_id})

                moderation_update = {
                    'action': 'restrict_user',
                    'user_id': reported_user_id,
                    'restricted_until': restriction_until.isoformat(),
                }

            elif action == 'suspend_user':
                suspend_type = str(data.get('suspend_type') or 'permanent').lower()
                if suspend_type not in {'temporary', 'permanent'}:
                    return jsonify({'error': 'suspend_type must be temporary or permanent'}), 400

                suspended_until = None
                if suspend_type == 'temporary':
                    suspended_until = _parse_iso_datetime_utc(data.get('suspend_until'))
                    if not suspended_until:
                        return jsonify({'error': 'suspend_until is required for temporary suspension'}), 400
                    if suspended_until <= datetime.now(timezone.utc):
                        return jsonify({'error': 'suspend_until must be in the future'}), 400

                conn.execute(text(
                    """
                    INSERT INTO user_moderation_state (user_id, suspended_permanent, suspended_until, reason, updated_by, updated_at)
                    VALUES (:uid, :is_perm, :until_ts, :reason, :actor, NOW())
                    ON CONFLICT (user_id) DO UPDATE
                    SET suspended_permanent = :is_perm,
                        suspended_until = :until_ts,
                        reason = :reason,
                        updated_by = :actor,
                        updated_at = NOW()
                    """
                ), {
                    'uid': reported_user_id,
                    'is_perm': suspend_type == 'permanent',
                    'until_ts': suspended_until,
                    'reason': verdict,
                    'actor': actor_id,
                })

                moderation_update = {
                    'action': 'suspend_user',
                    'user_id': reported_user_id,
                    'suspend_type': suspend_type,
                    'suspend_until': suspended_until.isoformat() if suspended_until else None,
                }

        if action == 'delete':
            if media_url and str(event_type or '').lower() == 'media':
                def _clean_public_id(pid: str) -> str:
                    if not pid:
                        return None
                    cleaned = pid.split('?', 1)[0]
                    if '/' in cleaned:
                        base, tail = cleaned.rsplit('/', 1)
                        if '.' in tail:
                            tail = tail.rsplit('.', 1)[0]
                        cleaned = f"{base}/{tail}" if base else tail
                    elif '.' in cleaned:
                        cleaned = cleaned.rsplit('.', 1)[0]
                    return cleaned or None

                public_id = _clean_public_id(cloudinary_id)
                if not public_id and ('cloudinary.com' in media_url or 'res.cloudinary' in media_url):
                    try:
                        parts = media_url.split('?')[0].split('/')
                        if 'upload' in parts:
                            upload_index = parts.index('upload')
                            if upload_index + 2 < len(parts):
                                if parts[upload_index + 1].startswith('v'):
                                    public_id = '/'.join(parts[upload_index + 2:])
                                else:
                                    public_id = '/'.join(parts[upload_index + 1:])
                        public_id = _clean_public_id(public_id)
                    except Exception:
                        public_id = None
                if public_id:
                    try:
                        from cloud_storage import delete_file
                        delete_result = delete_file(public_id)
                        media_deleted = bool(delete_result.get('success'))
                    except Exception:
                        media_deleted = False

            deleted_tags_total = 0
            if _reg_exists('event_tags'):
                try:
                    res_t = conn.execute(_sql_text(
                        "DELETE FROM event_tags WHERE event_id = :eid"
                    ), { 'eid': event_id_for_report })
                    deleted_tags_total += int(getattr(res_t, 'rowcount', 0) or 0)
                except Exception:
                    pass
            elif _reg_exists('event_tag'):
                try:
                    res_t = conn.execute(_sql_text(
                        "DELETE FROM event_tag WHERE event_id = :eid"
                    ), { 'eid': event_id_for_report })
                    deleted_tags_total += int(getattr(res_t, 'rowcount', 0) or 0)
                except Exception:
                    pass

            deleted_blocklist_total = 0
            if _reg_exists('timeline_block_list'):
                try:
                    res_b = conn.execute(_sql_text(
                        "DELETE FROM timeline_block_list WHERE event_id = :eid"
                    ), { 'eid': event_id_for_report })
                    deleted_blocklist_total = int(getattr(res_b, 'rowcount', 0) or 0)
                except Exception:
                    pass

            try:
                res_e = conn.execute(_sql_text(
                    "DELETE FROM event WHERE id = :eid"
                ), { 'eid': event_id_for_report })
                deleted_event = (getattr(res_e, 'rowcount', 0) or 0) > 0
            except Exception:
                deleted_event = False

            full_delete_required = False
            full_delete_reason = None

        try:
            from sqlalchemy import text as _sql_text
            rm_rows_resp = conn.execute(_sql_text(
                "SELECT timeline_id FROM timeline_block_list WHERE event_id = :eid"
            ), { 'eid': event_id_for_report }).all()
            removed_timeline_ids_resp = [int(r[0]) for r in rm_rows_resp]
        except Exception:
            removed_timeline_ids_resp = []

    return jsonify({
        'message': f'Report resolved with action {action}',
        'report_id': res['id'],
        'timeline_id': res['timeline_id'],
        'action': res['resolution'],
        'verdict': res['verdict'],
        'new_status': res['status'],
        'resolved_at': (res['resolved_at'].isoformat() if hasattr(res['resolved_at'], 'isoformat') else str(res['resolved_at'])),
        'safeguard_safe_until': (safeguard_safe_until.isoformat() if hasattr(safeguard_safe_until, 'isoformat') else None),
        'warning_until': (warning_until.isoformat() if hasattr(warning_until, 'isoformat') else None),
        'banned_timeline_id': banned_timeline_id,
        'full_delete_required': full_delete_required,
        'full_delete_reason': full_delete_reason,
        'event_id': event_id_for_report,
        'deleted_assoc_count': (deleted_assoc_count if action == 'remove' else deleted_assoc_total if action == 'delete' else None),
        'deleted_tags_count': (deleted_tags_total if action == 'delete' else None),
        'deleted_blocklist_count': (deleted_blocklist_total if action == 'delete' else None),
        'deleted_event': (deleted_event if action == 'delete' else None),
        'media_deleted': (media_deleted if action == 'delete' else None),
        'moderation_update': moderation_update,
        'username_blocked': username_blocked,
        'blocked': (True if action == 'remove' else False),
        'removed_timeline_ids': removed_timeline_ids_resp
    }), 200


@reports_bp.route('/reports/<int:report_id>/timeline-unban', methods=['POST'])
@jwt_required()
def unban_timeline_from_report(report_id):
    """
    SiteOwner-only: reverse an existing timeline ban resolution.
    - Deactivates timeline_ban_state and matching timeline_name_blocklist entries.
    - Archives the original resolved report ticket.
    """
    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_report_policy_tables(engine)

    with engine.begin() as conn:
        has_access, role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403
        if role != 'SiteOwner':
            return jsonify({'error': 'Only SiteOwner can unban timelines from tickets'}), 403

        rep = conn.execute(text(
            """
            SELECT id, report_type, resolution, reported_timeline_id, timeline_id
            FROM reports
            WHERE id = :rid
            """
        ), {'rid': report_id}).mappings().first()
        if not rep:
            return jsonify({'error': 'Report not found'}), 404
        if str(rep.get('report_type') or '').lower() != 'timeline' or str(rep.get('resolution') or '').lower() != 'ban_timeline':
            return jsonify({'error': 'Report is not a timeline ban resolution'}), 400

        target_timeline_id = rep.get('reported_timeline_id') if rep.get('reported_timeline_id') is not None else rep.get('timeline_id')
        if target_timeline_id is None:
            return jsonify({'error': 'Timeline target missing on report'}), 400
        target_timeline_id = int(target_timeline_id)

        timeline_row = conn.execute(text(
            "SELECT name FROM timeline WHERE id = :tid LIMIT 1"
        ), {'tid': target_timeline_id}).mappings().first()
        normalized_name = _normalize_timeline_name_policy(timeline_row.get('name') if timeline_row else '')

        conn.execute(text(
            """
            UPDATE timeline_ban_state
            SET is_active = FALSE,
                updated_at = NOW(),
                updated_by = :actor
            WHERE timeline_id = :tid
            """
        ), {'tid': target_timeline_id, 'actor': get_user_id()})

        if normalized_name:
            conn.execute(text(
                """
                UPDATE timeline_name_blocklist
                SET is_active = FALSE,
                    created_by = :actor
                WHERE timeline_name_normalized = :name
                """
            ), {'name': normalized_name, 'actor': get_user_id()})

        conn.execute(text(
            """
            UPDATE reports
            SET status = 'archived',
                updated_at = NOW()
            WHERE id = :rid
            """
        ), {'rid': report_id})

    return jsonify({
        'success': True,
        'report_id': report_id,
        'timeline_id': target_timeline_id,
        'new_status': 'archived',
        'message': 'Timeline unbanned and ticket archived'
    }), 200


@reports_bp.route('/reports/<int:report_id>/timeline-warning-lift', methods=['POST'])
@jwt_required()
def lift_timeline_warning_from_report(report_id):
    """
    SiteOwner/SiteAdmin: deactivate timeline warning for a warning-resolved ticket.
    """
    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_report_policy_tables(engine)

    with engine.begin() as conn:
        has_access, _role = _require_site_admin(conn, get_jwt_identity())
        if not has_access:
            return jsonify({'error': 'Access denied'}), 403

        rep = conn.execute(text(
            """
            SELECT id, report_type, resolution, reported_timeline_id, timeline_id
            FROM reports
            WHERE id = :rid
            """
        ), {'rid': report_id}).mappings().first()
        if not rep:
            return jsonify({'error': 'Report not found'}), 404
        if str(rep.get('report_type') or '').lower() != 'timeline' or str(rep.get('resolution') or '').lower() != 'issue_warning':
            return jsonify({'error': 'Report is not a timeline warning resolution'}), 400

        target_timeline_id = rep.get('reported_timeline_id') if rep.get('reported_timeline_id') is not None else rep.get('timeline_id')
        if target_timeline_id is None:
            return jsonify({'error': 'Timeline target missing on report'}), 400
        target_timeline_id = int(target_timeline_id)

        conn.execute(text(
            """
            UPDATE timeline_warning_state
            SET is_active = FALSE,
                updated_at = NOW(),
                updated_by = :actor
            WHERE timeline_id = :tid
            """
        ), {'tid': target_timeline_id, 'actor': get_user_id()})

    return jsonify({
        'success': True,
        'report_id': report_id,
        'timeline_id': target_timeline_id,
        'message': 'Timeline warning lifted'
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/warning-state', methods=['GET'])
def get_timeline_warning_state(timeline_id):
    """
    Public warning status for timeline UI.
    Returns active warning metadata when warning_until is in the future.
    """
    engine = get_db_engine()
    _ensure_report_policy_tables(engine)

    with engine.begin() as conn:
        row = conn.execute(text(
            """
            SELECT warning_scope,
                   warning_reason_public,
                   mask_content,
                   warning_until,
                   is_active
            FROM timeline_warning_state
            WHERE timeline_id = :tid
              AND is_active = TRUE
              AND warning_until > NOW()
            LIMIT 1
            """
        ), {'tid': int(timeline_id)}).mappings().first()

    if not row:
        return jsonify({'active': False, 'timeline_id': int(timeline_id)}), 200

    return jsonify({
        'active': True,
        'timeline_id': int(timeline_id),
        'warning_scope': _normalize_warning_scope(row.get('warning_scope')),
        'warning_reason_public': row.get('warning_reason_public') or '',
        'mask_content': bool(row.get('mask_content')),
        'warning_until': (row['warning_until'].isoformat() if row.get('warning_until') and hasattr(row['warning_until'], 'isoformat') else (row.get('warning_until') and str(row['warning_until']) or None)),
        'is_indef': bool(row.get('warning_until') and hasattr(row.get('warning_until'), 'year') and row.get('warning_until').year >= 9999),
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/status-message', methods=['GET'])
def get_timeline_status_message(timeline_id):
    engine = get_db_engine()
    _ensure_timeline_status_message_table(engine)

    with engine.begin() as conn:
        row = conn.execute(text(
            """
            SELECT status_type,
                   status_header,
                   status_body,
                   is_active,
                   updated_at
            FROM timeline_status_message
            WHERE timeline_id = :tid
              AND is_active = TRUE
            LIMIT 1
            """
        ), {'tid': int(timeline_id)}).mappings().first()

    if not row:
        return jsonify({'active': False, 'timeline_id': int(timeline_id)}), 200

    return jsonify({
        'active': True,
        'timeline_id': int(timeline_id),
        'status_type': _normalize_status_message_type(row.get('status_type')),
        'status_header': row.get('status_header') or '',
        'status_body': row.get('status_body') or '',
        'updated_at': row.get('updated_at').isoformat() if row.get('updated_at') and hasattr(row.get('updated_at'), 'isoformat') else None
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/status-message', methods=['PUT'])
@jwt_required()
def update_timeline_status_message(timeline_id):
    engine = get_db_engine()
    _ensure_timeline_status_message_table(engine)

    _, _membership, has_access = check_timeline_access(timeline_id, required_role='moderator')
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    status_type = _normalize_status_message_type(data.get('status_type'))
    status_header = (data.get('status_header') or '').strip()
    status_body = (data.get('status_body') or '').strip()

    if status_header:
        header_words = [w for w in status_header.split() if w]
        if len(header_words) > STATUS_HEADER_WORD_LIMIT:
            return jsonify({'error': f'Status header must be {STATUS_HEADER_WORD_LIMIT} words or less'}), 400
        if len(status_header) > STATUS_HEADER_MAX_CHARS:
            return jsonify({'error': f'Status header must be {STATUS_HEADER_MAX_CHARS} characters or less'}), 400

    if status_body and len(status_body) > STATUS_BODY_MAX_CHARS:
        return jsonify({'error': f'Status body must be {STATUS_BODY_MAX_CHARS} characters or less'}), 400

    is_active = bool(status_type and (status_header or status_body))

    with engine.begin() as conn:
        conn.execute(text(
            """
            INSERT INTO timeline_status_message (
                timeline_id,
                status_type,
                status_header,
                status_body,
                is_active,
                updated_by,
                updated_at,
                created_at
            )
            VALUES (
                :timeline_id,
                :status_type,
                :status_header,
                :status_body,
                :is_active,
                :updated_by,
                NOW(),
                NOW()
            )
            ON CONFLICT (timeline_id) DO UPDATE
            SET status_type = EXCLUDED.status_type,
                status_header = EXCLUDED.status_header,
                status_body = EXCLUDED.status_body,
                is_active = EXCLUDED.is_active,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            """
        ), {
            'timeline_id': int(timeline_id),
            'status_type': status_type,
            'status_header': status_header or None,
            'status_body': status_body or None,
            'is_active': is_active,
            'updated_by': get_user_id(),
        })

    return jsonify({
        'success': True,
        'timeline_id': int(timeline_id),
        'active': is_active,
        'status_type': status_type,
        'status_header': status_header,
        'status_body': status_body,
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/reports', methods=['POST'])
def submit_report(timeline_id):
    """
    Level 1 placeholder: Submit a report for a post/event.
    - Authentication: optional. If JWT present, capture reporter_id; else mark as anonymous.
    - Body: { event_id: number, reason?: string }
    - No DB writes yet; returns structured response for frontend wiring.
    """
    # Try to read optional JWT
    reporter_id = None
    try:
        verify_jwt_in_request(optional=True)
        reporter_id = get_jwt_identity()
    except Exception:
        reporter_id = None

    data = request.get_json(silent=True) or {}
    event_id = data.get('event_id')
    reason = (data.get('reason') or '').strip()
    category_raw = (data.get('category') or '').strip().lower()
    allowed_categories = {'website_policy', 'government_policy', 'unethical_boundary'}
    category = category_raw if category_raw in allowed_categories else None

    # Basic validation
    if not event_id:
        return jsonify({'error': 'event_id is required'}), 400

    logger.info(
        f"REPORT submit: reporter={reporter_id if reporter_id is not None else 'anonymous'} "
        f"timeline={timeline_id} event_id={event_id} reason_len={len(reason)} category={category or 'none'}"
    )

    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_user_moderation_tables(engine)
    _ensure_report_policy_tables(engine)

    with engine.begin() as conn:
        if reporter_id is not None:
            restricted_msg = _get_report_submission_restriction(conn, reporter_id)
            if restricted_msg:
                return jsonify({'error': restricted_msg}), 403

        try:
            event_owner = conn.execute(text(
                "SELECT user_id FROM event WHERE id = :eid LIMIT 1"
            ), {'eid': int(event_id)}).mappings().first()
        except Exception:
            event_owner = None

        owner_user_id = event_owner.get('user_id') if event_owner else None
        is_protected_owner, protected_role = _is_site_protected_user(conn, owner_user_id)
        if is_protected_owner:
            return jsonify({
                'error': f'{protected_role} accounts cannot be reported',
                'code': 'PROTECTED_ACCOUNT_NOT_REPORTABLE'
            }), 403

        active_lock = _get_active_safeguard_lock(
            conn,
            target_type='post',
            target_id=int(event_id),
            scopes=[f'community_timeline:{int(timeline_id)}', 'site_global']
        )
        if active_lock:
            safe_until = active_lock.get('safe_until')
            return jsonify({
                'error': 'Reporting is temporarily disabled for this item',
                'code': 'REPORT_SAFEGUARD_ACTIVE',
                'scope': active_lock.get('scope'),
                'safe_until': (safe_until.isoformat() if hasattr(safe_until, 'isoformat') else str(safe_until))
            }), 429

        existing_report_id = _get_open_report_id(
            conn,
            "COALESCE(report_type, 'post') = 'post' AND event_id = :event_id AND timeline_id = :timeline_id",
            {'event_id': int(event_id), 'timeline_id': int(timeline_id)}
        )
        if existing_report_id:
            return jsonify({
                'error': 'An open report already exists for this item',
                'code': 'REPORT_ALREADY_OPEN',
                'report_id': existing_report_id
            }), 409

        row = conn.execute(text(
            """
            INSERT INTO reports (timeline_id, event_id, reporter_id, reason, status)
            VALUES (:timeline_id, :event_id, :reporter_id, :reason, 'pending')
            RETURNING id, created_at
            """
        ), {
            'timeline_id': timeline_id,
            'event_id': int(event_id),
            'reporter_id': reporter_id,
            'reason': (f"[{category}] " if category else "") + reason,
        }).mappings().first()

    return jsonify({
        'success': True,
        'timeline_id': timeline_id,
        'event_id': int(event_id),
        'reason': (f"[{category}] " if category else "") + reason,
        'reporter_id': reporter_id,
        'status': 'pending',
        'report_id': row['id'],
        'received_at': (row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']))
    }), 200


@reports_bp.route('/reports/users/<int:reported_user_id>', methods=['POST'])
def submit_user_report(reported_user_id):
    """
    Submit a user-focused report ticket for Site Control workflows.
    Authentication optional: if JWT exists, capture reporter_id.
    Body: { timeline_id?: number, reason?: string, category?: string }
    timeline_id is optional for profile-driven reports and defaults to -1.
    """
    reporter_id = None
    try:
        verify_jwt_in_request(optional=True)
        reporter_id = get_jwt_identity()
    except Exception:
        reporter_id = None

    data = request.get_json(silent=True) or {}
    timeline_id = data.get('timeline_id')
    reason = (data.get('reason') or '').strip()
    category_raw = (data.get('category') or '').strip().lower()
    allowed_categories = {'website_policy', 'government_policy', 'unethical_boundary'}
    category = category_raw if category_raw in allowed_categories else None

    try:
        timeline_id = int(timeline_id) if timeline_id not in (None, '') else -1
    except (TypeError, ValueError):
        return jsonify({'error': 'timeline_id must be an integer when provided'}), 400

    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_user_moderation_tables(engine)
    _ensure_report_policy_tables(engine)

    with engine.begin() as conn:
        if reporter_id is not None:
            restricted_msg = _get_report_submission_restriction(conn, reporter_id)
            if restricted_msg:
                return jsonify({'error': restricted_msg}), 403

        is_protected_user, protected_role = _is_site_protected_user(conn, reported_user_id)
        if is_protected_user:
            return jsonify({
                'error': f'{protected_role} accounts cannot be reported',
                'code': 'PROTECTED_ACCOUNT_NOT_REPORTABLE'
            }), 403

        active_lock = _get_active_safeguard_lock(
            conn,
            target_type='user',
            target_id=int(reported_user_id),
            scopes=['site_global']
        )
        if active_lock:
            safe_until = active_lock.get('safe_until')
            return jsonify({
                'error': 'Reporting is temporarily disabled for this user',
                'code': 'REPORT_SAFEGUARD_ACTIVE',
                'scope': active_lock.get('scope'),
                'safe_until': (safe_until.isoformat() if hasattr(safe_until, 'isoformat') else str(safe_until))
            }), 429

        existing_report_id = _get_open_report_id(
            conn,
            "report_type = 'user' AND reported_user_id = :reported_user_id",
            {'reported_user_id': int(reported_user_id)}
        )
        if existing_report_id:
            return jsonify({
                'error': 'An open report already exists for this user',
                'code': 'REPORT_ALREADY_OPEN',
                'report_id': existing_report_id
            }), 409

        row = conn.execute(text(
            """
            INSERT INTO reports (
                timeline_id,
                event_id,
                reporter_id,
                report_type,
                reported_user_id,
                reason,
                status
            )
            VALUES (
                :timeline_id,
                NULL,
                :reporter_id,
                'user',
                :reported_user_id,
                :reason,
                'pending'
            )
            RETURNING id, created_at
            """
        ), {
            'timeline_id': timeline_id,
            'reporter_id': reporter_id,
            'reported_user_id': int(reported_user_id),
            'reason': (f"[{category}] " if category else "") + reason,
        }).mappings().first()

    return jsonify({
        'success': True,
        'timeline_id': timeline_id,
        'event_id': None,
        'report_type': 'user',
        'reported_user_id': int(reported_user_id),
        'reason': (f"[{category}] " if category else "") + reason,
        'reporter_id': reporter_id,
        'status': 'pending',
        'report_id': row['id'],
        'received_at': (row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']))
    }), 200


@reports_bp.route('/reports/timelines/<int:reported_timeline_id>', methods=['POST'])
def submit_timeline_report(reported_timeline_id):
    """
    Submit a timeline-focused report ticket for Site Control workflows.
    Authentication optional: if JWT exists, capture reporter_id.
    Body: { reason?: string, category?: string }
    """
    reporter_id = None
    try:
        verify_jwt_in_request(optional=True)
        reporter_id = get_jwt_identity()
    except Exception:
        reporter_id = None

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()
    category_raw = (data.get('category') or '').strip().lower()
    allowed_categories = {'website_policy', 'government_policy', 'unethical_boundary'}
    category = category_raw if category_raw in allowed_categories else None

    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_user_moderation_tables(engine)
    _ensure_report_policy_tables(engine)

    with engine.begin() as conn:
        if reporter_id is not None:
            restricted_msg = _get_report_submission_restriction(conn, reporter_id)
            if restricted_msg:
                return jsonify({'error': restricted_msg}), 403

        timeline_row = conn.execute(text(
            "SELECT id, created_by FROM timeline WHERE id = :tid LIMIT 1"
        ), {'tid': int(reported_timeline_id)}).mappings().first()
        if not timeline_row:
            return jsonify({'error': 'Timeline not found'}), 404

        is_protected_owner, protected_role = _is_site_protected_user(conn, timeline_row.get('created_by'))
        if is_protected_owner:
            return jsonify({
                'error': f'{protected_role} timelines cannot be reported',
                'code': 'PROTECTED_TIMELINE_NOT_REPORTABLE'
            }), 403

        active_lock = _get_active_safeguard_lock(
            conn,
            target_type='timeline',
            target_id=int(reported_timeline_id),
            scopes=[f'community_timeline:{int(reported_timeline_id)}', 'site_global']
        )
        if active_lock:
            safe_until = active_lock.get('safe_until')
            return jsonify({
                'error': 'Reporting is temporarily disabled for this timeline',
                'code': 'REPORT_SAFEGUARD_ACTIVE',
                'scope': active_lock.get('scope'),
                'safe_until': (safe_until.isoformat() if hasattr(safe_until, 'isoformat') else str(safe_until))
            }), 429

        existing_report_id = _get_open_report_id(
            conn,
            "report_type = 'timeline' AND reported_timeline_id = :reported_timeline_id",
            {'reported_timeline_id': int(reported_timeline_id)}
        )
        if existing_report_id:
            return jsonify({
                'error': 'An open report already exists for this timeline',
                'code': 'REPORT_ALREADY_OPEN',
                'report_id': existing_report_id
            }), 409

        row = conn.execute(text(
            """
            INSERT INTO reports (
                timeline_id,
                event_id,
                reporter_id,
                report_type,
                reported_timeline_id,
                reason,
                status
            )
            VALUES (
                :timeline_id,
                NULL,
                :reporter_id,
                'timeline',
                :reported_timeline_id,
                :reason,
                'pending'
            )
            RETURNING id, created_at
            """
        ), {
            'timeline_id': int(reported_timeline_id),
            'reporter_id': reporter_id,
            'reported_timeline_id': int(reported_timeline_id),
            'reason': (f"[{category}] " if category else "") + reason,
        }).mappings().first()

    return jsonify({
        'success': True,
        'timeline_id': int(reported_timeline_id),
        'event_id': None,
        'report_type': 'timeline',
        'reported_timeline_id': int(reported_timeline_id),
        'reason': (f"[{category}] " if category else "") + reason,
        'reporter_id': reporter_id,
        'status': 'pending',
        'report_id': row['id'],
        'received_at': (row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']))
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/reports/<int:report_id>/accept', methods=['POST'])
@jwt_required()
def accept_report(timeline_id, report_id):
    """
    Placeholder: Accept a report for review.
    - No DB writes yet; returns a structured success response.
    - Enforces moderator+ access.
    """
    timeline_row, membership_row, has_access = check_timeline_access(timeline_id, required_role='moderator')
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    actor_id = get_user_id()
    engine = get_db_engine()
    _ensure_reports_table(engine)

    with engine.begin() as conn:
        res = conn.execute(text(
            """
            UPDATE reports
            SET status = 'reviewing', assigned_to = :actor, updated_at = NOW()
            WHERE id = :rid AND timeline_id = :tid
            RETURNING id, status, assigned_to, updated_at
            """
        ), {'actor': actor_id, 'rid': report_id, 'tid': timeline_id}).mappings().first()
        if not res:
            return jsonify({'error': 'Report not found'}), 404

    return jsonify({
        'message': 'Accepted for review',
        'report_id': res['id'],
        'timeline_id': timeline_id,
        'assigned_to': res['assigned_to'],
        'new_status': res['status'],
        'timestamp': (res['updated_at'].isoformat() if hasattr(res['updated_at'], 'isoformat') else str(res['updated_at']))
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/reports/<int:report_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_report(timeline_id, report_id):
    """
    Resolve a report by taking an action and persisting a moderator verdict.
    - Body: { action: 'remove' | 'delete' | 'safeguard', verdict: string }
    - For action 'remove': perform timeline-only removal (unshare) of the event from this timeline.
    - Returns full_delete_required flag when the event is no longer associated with any timelines after removal.
    - Enforces moderator+ access.
    """
    timeline_row, membership_row, has_access = check_timeline_access(timeline_id, required_role='moderator')
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    action = str(data.get('action', '')).lower()
    if action not in {'remove', 'delete', 'safeguard'}:
        return jsonify({'error': 'Invalid action'}), 400
    verdict = (data.get('verdict') or '').strip()
    # Verdict is mandatory for all resolve actions per policy
    if not verdict:
        return jsonify({'error': 'verdict is required'}), 400

    actor_id = get_user_id()
    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_report_policy_tables(engine)

    full_delete_required = False
    full_delete_reason = None
    event_id_for_report = None
    safeguard_safe_until = None
    # Deletion metrics (populated when action == 'delete')
    deleted_event = False
    deleted_assoc_total = None
    deleted_tags_total = None
    deleted_blocklist_total = None

    with engine.begin() as conn:
        # Fetch the event_id for this report first
        rep = conn.execute(text(
            """
            SELECT event_id FROM reports WHERE id = :rid AND timeline_id = :tid
            """
        ), {'rid': report_id, 'tid': timeline_id}).mappings().first()
        if not rep:
            return jsonify({'error': 'Report not found'}), 404
        event_id_for_report = int(rep['event_id'])

        # Legacy single-timeline guard removed; rely on robust exists-elsewhere rule below

        # Update the report with resolution and verdict
        res = conn.execute(text(
            """
            UPDATE reports
            SET status = 'resolved',
                resolution = :action,
                verdict = :verdict,
                resolved_at = NOW(),
                updated_at = NOW(),
                assigned_to = COALESCE(assigned_to, :actor)
            WHERE id = :rid AND timeline_id = :tid
            RETURNING id, status, resolution, verdict, resolved_at
            """
        ), {'action': action, 'verdict': verdict, 'actor': actor_id, 'rid': report_id, 'tid': timeline_id}).mappings().first()
        if not res:
            return jsonify({'error': 'Report not found'}), 404

        if action == 'safeguard':
            parsed_until, parse_err = _parse_safeguard_until(data, allow_custom=False)
            if parse_err:
                return jsonify({'error': parse_err}), 400
            safeguard_safe_until = parsed_until
            conn.execute(text(
                """
                INSERT INTO report_safeguard_cooldown (
                    target_type,
                    target_id,
                    scope,
                    safe_until,
                    source_report_id,
                    created_by,
                    is_active
                )
                VALUES (
                    'post',
                    :target_id,
                    :scope,
                    :safe_until,
                    :source_report_id,
                    :created_by,
                    TRUE
                )
                ON CONFLICT (source_report_id) DO UPDATE
                SET target_type = EXCLUDED.target_type,
                    target_id = EXCLUDED.target_id,
                    scope = EXCLUDED.scope,
                    safe_until = EXCLUDED.safe_until,
                    created_by = EXCLUDED.created_by,
                    is_active = TRUE
                """
            ), {
                'target_id': event_id_for_report,
                'scope': f'community_timeline:{int(timeline_id)}',
                'safe_until': safeguard_safe_until,
                'source_report_id': int(report_id),
                'created_by': actor_id,
            })

        # If action is 'remove', enforce blocklist-based removal with "exists elsewhere" rule
        if action == 'remove':
            from sqlalchemy import text as _sql_text
            # Ensure block list table exists
            try:
                conn.execute(_sql_text(
                    """
                    CREATE TABLE IF NOT EXISTS timeline_block_list (
                        event_id INTEGER NOT NULL,
                        timeline_id INTEGER NOT NULL,
                        removed_by INTEGER NULL,
                        removed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (event_id, timeline_id)
                    )
                    """
                ))
            except Exception:
                pass

            # Build candidate timelines: owner + associations + hashtag timelines by tag name
            # Owner
            owner_row = conn.execute(_sql_text("SELECT timeline_id FROM event WHERE id = :eid"), { 'eid': event_id_for_report }).first()
            owner_id = int(owner_row[0]) if owner_row and owner_row[0] is not None else None
            active_ids = set()
            if owner_id:
                active_ids.add(owner_id)

            # Explicit associations
            assoc_rows = conn.execute(_sql_text(
                "SELECT DISTINCT timeline_id FROM event_timeline_association WHERE event_id = :eid"
            ), { 'eid': event_id_for_report }).all()
            for r in assoc_rows:
                if r and r[0] is not None:
                    active_ids.add(int(r[0]))

            # Hashtag timelines by tags (materialized timelines)
            # Check table existence to avoid aborting the transaction
            def _reg_exists(tbl: str) -> bool:
                try:
                    rr = conn.execute(_sql_text("SELECT to_regclass(:t)"), { 't': f'public.{tbl}' }).first()
                    return bool(rr and rr[0])
                except Exception:
                    return False

            tag_count = 0
            if _reg_exists('event_tags'):
                cnt = conn.execute(_sql_text("SELECT COUNT(*) FROM event_tags WHERE event_id = :eid"), { 'eid': event_id_for_report }).first()
                tag_count = int(cnt[0]) if cnt and cnt[0] is not None else 0
            elif _reg_exists('event_tag'):
                cnt = conn.execute(_sql_text("SELECT COUNT(*) FROM event_tag WHERE event_id = :eid"), { 'eid': event_id_for_report }).first()
                tag_count = int(cnt[0]) if cnt and cnt[0] is not None else 0

            # Try to map tag names to timelines using only existing tables
            tag_names = []
            if tag_count > 0:
                candidates = []
                if _reg_exists('tags') and _reg_exists('event_tags'):
                    candidates.append("SELECT t.name FROM tags t JOIN event_tags et ON et.tag_id = t.id WHERE et.event_id = :eid")
                if _reg_exists('tags') and _reg_exists('event_tag'):
                    candidates.append("SELECT t.name FROM tags t JOIN event_tag et ON et.tag_id = t.id WHERE et.event_id = :eid")
                if _reg_exists('tag') and _reg_exists('event_tags'):
                    candidates.append("SELECT t.name FROM tag t JOIN event_tags et ON et.tag_id = t.id WHERE et.event_id = :eid")
                if _reg_exists('tag') and _reg_exists('event_tag'):
                    candidates.append("SELECT t.name FROM tag t JOIN event_tag et ON et.tag_id = t.id WHERE et.event_id = :eid")
                for q in candidates:
                    rows = conn.execute(_sql_text(q), { 'eid': event_id_for_report }).all()
                    names = [str(r[0]) for r in rows if r and r[0]]
                    if names:
                        tag_names = names
                        break
            if tag_names:
                # Avoid array binding issues: query per-name to prevent aborting the transaction
                for nm in list({ n.lower() for n in tag_names if n }):
                    try:
                        tlr = conn.execute(_sql_text(
                            "SELECT id FROM timeline WHERE LOWER(name) = :name"
                        ), { 'name': nm }).first()
                        if tlr and tlr[0] is not None:
                            active_ids.add(int(tlr[0]))
                    except Exception:
                        continue

            # Subtract already blocked timelines
            blocked_rows = conn.execute(_sql_text(
                "SELECT timeline_id FROM timeline_block_list WHERE event_id = :eid"
            ), { 'eid': event_id_for_report }).all()
            blocked_ids = { int(r[0]) for r in blocked_rows if r and r[0] is not None }
            effective_active_ids = { i for i in active_ids if i not in blocked_ids }
            other_active_ids = { i for i in effective_active_ids if i != timeline_id }

            # Enforce rule: can remove only if exists elsewhere.
            # We consider two signals:
            # 1) effective_active_ids > 1 (owner + associations + hashtag timelines that exist in DB minus blocked)
            # 2) distinct tag names > 1 (counts as existing elsewhere even if hashtag timelines haven't been materialized yet)
            exists_elsewhere = (len(other_active_ids) >= 1) or (tag_count >= 2)
            # Do not require current timeline to be active; if the event exists elsewhere, allow removal.
            if not exists_elsewhere:
                return jsonify({
                    'error': 'Removal denied: event would have no remaining placements after removal',
                    'event_id': event_id_for_report,
                    'timeline_id': timeline_id,
                    'effective_active_ids': list(sorted(effective_active_ids)),
                    'other_active_ids': list(sorted(other_active_ids)),
                    'tag_count': tag_count
                }), 409

            # Insert into block list
            try:
                actor_id = get_jwt_identity()
            except Exception:
                actor_id = None
            conn.execute(_sql_text(
                """
                INSERT INTO timeline_block_list (event_id, timeline_id, removed_by)
                VALUES (:eid, :tid, :actor)
                ON CONFLICT (event_id, timeline_id) DO NOTHING
                """
            ), { 'eid': event_id_for_report, 'tid': timeline_id, 'actor': actor_id })

            # Optionally remove association row for cleanliness (not source of truth anymore)
            del_res = conn.execute(_sql_text(
                """
                DELETE FROM event_timeline_association
                WHERE event_id = :eid AND timeline_id = :tid
                """
            ), { 'eid': event_id_for_report, 'tid': timeline_id })
            deleted_assoc_count = getattr(del_res, 'rowcount', None)

            # Recompute remaining active after block to inform full-delete hint
            blocked_ids_after = blocked_ids | { timeline_id }
            remaining_after = { i for i in active_ids if i not in blocked_ids_after }
            if len(remaining_after) == 0:
                full_delete_required = True
                full_delete_reason = 'Event is blocked on all timelines'

        elif action == 'delete':
            # Perform a full delete of the event and related records
            from sqlalchemy import text as _sql_text
            # Best-effort deletes guarded by table existence
            def _reg_exists(tbl: str) -> bool:
                try:
                    rr = conn.execute(_sql_text("SELECT to_regclass(:t)"), { 't': f'public.{tbl}' }).first()
                    return bool(rr and rr[0])
                except Exception:
                    return False

            # Delete associations to timelines
            deleted_assoc_total = 0
            if _reg_exists('event_timeline_association'):
                try:
                    res_a = conn.execute(_sql_text(
                        "DELETE FROM event_timeline_association WHERE event_id = :eid"
                    ), { 'eid': event_id_for_report })
                    deleted_assoc_total = int(getattr(res_a, 'rowcount', 0) or 0)
                except Exception:
                    pass

            # Delete tag links (support both event_tags and event_tag)
            deleted_tags_total = 0
            if _reg_exists('event_tags'):
                try:
                    res_t = conn.execute(_sql_text(
                        "DELETE FROM event_tags WHERE event_id = :eid"
                    ), { 'eid': event_id_for_report })
                    deleted_tags_total += int(getattr(res_t, 'rowcount', 0) or 0)
                except Exception:
                    pass
            elif _reg_exists('event_tag'):
                try:
                    res_t = conn.execute(_sql_text(
                        "DELETE FROM event_tag WHERE event_id = :eid"
                    ), { 'eid': event_id_for_report })
                    deleted_tags_total += int(getattr(res_t, 'rowcount', 0) or 0)
                except Exception:
                    pass

            # Delete blocklist entries
            deleted_blocklist_total = 0
            if _reg_exists('timeline_block_list'):
                try:
                    res_b = conn.execute(_sql_text(
                        "DELETE FROM timeline_block_list WHERE event_id = :eid"
                    ), { 'eid': event_id_for_report })
                    deleted_blocklist_total = int(getattr(res_b, 'rowcount', 0) or 0)
                except Exception:
                    pass

            # Finally delete the event itself
            try:
                res_e = conn.execute(_sql_text(
                    "DELETE FROM event WHERE id = :eid"
                ), { 'eid': event_id_for_report })
                deleted_event = (getattr(res_e, 'rowcount', 0) or 0) > 0
            except Exception:
                deleted_event = False

            # For delete, by definition, nothing remains
            full_delete_required = False
            full_delete_reason = None

        # Fetch removed_timeline_ids for response context (must stay inside the connection scope)
        try:
            from sqlalchemy import text as _sql_text
            rm_rows_resp = conn.execute(_sql_text(
                "SELECT timeline_id FROM timeline_block_list WHERE event_id = :eid"
            ), { 'eid': event_id_for_report }).all()
            removed_timeline_ids_resp = [int(r[0]) for r in rm_rows_resp]
        except Exception:
            removed_timeline_ids_resp = []

    return jsonify({
        'message': f'Report resolved with action {action}',
        'report_id': res['id'],
        'timeline_id': timeline_id,
        'action': res['resolution'],
        'verdict': res['verdict'],
        'new_status': res['status'],
        'resolved_at': (res['resolved_at'].isoformat() if hasattr(res['resolved_at'], 'isoformat') else str(res['resolved_at'])),
        'safeguard_safe_until': (safeguard_safe_until.isoformat() if hasattr(safeguard_safe_until, 'isoformat') else None),
        'full_delete_required': full_delete_required,
        'full_delete_reason': full_delete_reason,
        'event_id': event_id_for_report,
        # For observability in clients/tests when action == 'remove'
        'deleted_assoc_count': (deleted_assoc_count if action == 'remove' else deleted_assoc_total if action == 'delete' else None),
        'deleted_tags_count': (deleted_tags_total if action == 'delete' else None),
        'deleted_blocklist_count': (deleted_blocklist_total if action == 'delete' else None),
        'deleted_event': (deleted_event if action == 'delete' else None),
        'blocked': (True if action == 'remove' else False),
        'removed_timeline_ids': removed_timeline_ids_resp
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/reports/<int:report_id>/assign', methods=['POST'])
@jwt_required()
def assign_report(timeline_id, report_id):
    """
    Placeholder: Assign a report to a moderator.
    - Body: { moderator_id }
    - No DB writes yet; returns structured response.
    - Enforces moderator+ access.
    """
    timeline_row, membership_row, has_access = check_timeline_access(timeline_id, required_role='moderator')
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    moderator_id = data.get('moderator_id')
    if not moderator_id:
        return jsonify({'error': 'moderator_id is required'}), 400

    actor_id = get_user_id()
    logger.info(f"ASSIGN report placeholder: actor={actor_id} timeline={timeline_id} report={report_id} moderator_id={moderator_id}")

    return jsonify({
        'message': 'Report assigned (placeholder)',
        'report_id': report_id,
        'timeline_id': timeline_id,
        'assigned_to': moderator_id,
        'timestamp': datetime.now().isoformat()
    }), 200
