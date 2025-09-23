from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, verify_jwt_in_request, get_jwt_identity
from datetime import datetime
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
                event_id INTEGER NOT NULL,
                reporter_id INTEGER NULL,
                reason TEXT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending',
                assigned_to INTEGER NULL,
                resolution VARCHAR(16) NULL,
                verdict TEXT NULL,
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
    return s if s in {'all', 'pending', 'reviewing', 'resolved'} else 'all'


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

    where_clause = "WHERE timeline_id = :timeline_id"
    params = { 'timeline_id': timeline_id }
    if status != 'all':
        where_clause += " AND status = :status"
        params['status'] = status

    # Counts per status
    with engine.begin() as conn:
        counts = {}
        for st in ['pending', 'reviewing', 'resolved']:
            res = conn.execute(text("SELECT COUNT(*) FROM reports WHERE timeline_id = :tid AND status = :st"),
                               {'tid': timeline_id, 'st': st}).scalar() or 0
            counts[st] = int(res)
        total_all = conn.execute(text("SELECT COUNT(*) FROM reports WHERE timeline_id = :tid"),
                                 {'tid': timeline_id}).scalar() or 0

        # Pagination
        offset = (page - 1) * page_size
        # Include reporter username and avatar via LEFT JOIN to user table (non-breaking)
        items = conn.execute(text(
            f"""
            SELECT r.id,
                   r.timeline_id,
                   r.event_id,
                   r.reporter_id,
                   r.reason,
                   r.status,
                   r.assigned_to,
                   r.resolution,
                   r.verdict,
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

    with engine.begin() as conn:
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
                }), 400

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
        'deleted_assoc_count': (deleted_assoc_count if action == 'remove' else None),
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
