from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, verify_jwt_in_request, get_jwt_identity
from datetime import datetime, timezone
import logging
from sqlalchemy import text
from utils.db_helper import get_db_engine

# We import helpers from community routes for consistent access control semantics
from routes.community import check_timeline_access, get_user_id

reports_bp = Blueprint('reports', __name__)
logger = logging.getLogger(__name__)


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
                   u.username AS reporter_username,
                   u.avatar_url AS reporter_avatar_url,
                   a.username AS assigned_to_username,
                   a.avatar_url AS assigned_to_avatar_url
            FROM reports r
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
            'avatar_url': r.get('avatar_url'),
        })

    return jsonify({'items': items}), 200


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
    if action not in {'remove', 'delete', 'safeguard', 'edit', 'require_username_change', 'restrict_user', 'suspend_user'}:
        return jsonify({'error': 'Invalid action'}), 400
    verdict = (data.get('verdict') or '').strip()
    lock_edit = bool(data.get('lock_edit'))
    if not verdict:
        return jsonify({'error': 'verdict is required'}), 400

    engine = get_db_engine()
    _ensure_reports_table(engine)
    _ensure_user_moderation_tables(engine)

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
        if report_type == 'post' and action in {'require_username_change', 'restrict_user', 'suspend_user'}:
            return jsonify({'error': f"Action '{action}' is only supported for user tickets"}), 400
        if report_type == 'user' and action in {'delete', 'remove', 'edit'}:
            return jsonify({'error': f"Action '{action}' is only supported for post tickets"}), 400
        if report_type not in {'post', 'user'} and action in {'delete', 'remove', 'edit', 'require_username_change', 'restrict_user', 'suspend_user'}:
            return jsonify({'error': f"Action '{action}' is not supported for this ticket type"}), 400

        event_id_for_report = int(rep['event_id']) if rep.get('event_id') is not None else None
        timeline_id = int(rep['timeline_id']) if rep.get('timeline_id') is not None else None
        reported_user_id = int(rep['reported_user_id']) if rep.get('reported_user_id') is not None else None

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

    full_delete_required = False
    full_delete_reason = None
    event_id_for_report = None
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
