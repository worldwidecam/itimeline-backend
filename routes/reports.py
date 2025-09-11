from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, verify_jwt_in_request, get_jwt_identity
from datetime import datetime
import logging

# We import helpers from community routes for consistent access control semantics
from routes.community import check_timeline_access, get_user_id

reports_bp = Blueprint('reports', __name__)
logger = logging.getLogger(__name__)


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

    # Placeholder data shape for frontend wiring
    data = {
        'items': [],              # Array of report objects (empty for now)
        'status': status,         # Echo filter
        'page': page,
        'page_size': page_size,
        'total': 0,               # Total matching items
        'counts': {               # Tab counts for convenience
            'all': 0,
            'pending': 0,
            'reviewing': 0,
            'resolved': 0,
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

    # Basic validation
    if not event_id:
        return jsonify({'error': 'event_id is required'}), 400

    logger.info(
        f"REPORT submit placeholder: reporter={reporter_id if reporter_id is not None else 'anonymous'} "
        f"timeline={timeline_id} event_id={event_id} reason_len={len(reason)}"
    )

    # Placeholder response
    return jsonify({
        'success': True,
        'timeline_id': timeline_id,
        'event_id': event_id,
        'reason': reason,
        'reporter_id': reporter_id,  # can be None for anonymous
        'status': 'pending',
        'received_at': datetime.now().isoformat()
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
    logger.info(f"ACCEPT report placeholder: actor={actor_id} timeline={timeline_id} report={report_id}")

    return jsonify({
        'message': 'Accepted for review (placeholder)',
        'report_id': report_id,
        'timeline_id': timeline_id,
        'assigned_to': actor_id,
        'new_status': 'reviewing',
        'timestamp': datetime.now().isoformat()
    }), 200


@reports_bp.route('/timelines/<int:timeline_id>/reports/<int:report_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_report(timeline_id, report_id):
    """
    Placeholder: Resolve a report by deleting or safeguarding the post.
    - Body: { action: 'delete' | 'safeguard' }
    - No DB writes yet; returns structured response.
    - Enforces moderator+ access.
    """
    timeline_row, membership_row, has_access = check_timeline_access(timeline_id, required_role='moderator')
    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    data = request.get_json(silent=True) or {}
    action = str(data.get('action', '')).lower()
    if action not in {'delete', 'safeguard'}:
        return jsonify({'error': 'Invalid action'}), 400

    actor_id = get_user_id()
    logger.info(f"RESOLVE report placeholder: actor={actor_id} timeline={timeline_id} report={report_id} action={action}")

    return jsonify({
        'message': f'Report resolved with action {action} (placeholder)',
        'report_id': report_id,
        'timeline_id': timeline_id,
        'action': action,
        'new_status': 'resolved',
        'timestamp': datetime.now().isoformat()
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
