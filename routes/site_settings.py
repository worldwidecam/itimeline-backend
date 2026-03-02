from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import text
import json
import logging

from utils.db_helper import get_db_engine

site_settings_bp = Blueprint('site_settings', __name__)
logger = logging.getLogger(__name__)

DEFAULT_LEAD_SENTENCE = "Create personal timelines or entire communities to keep track of..."
DEFAULT_ROTATOR = [
    "your marriage",
    "family memories",
    "an upcoming video game",
    "Survivor",
    "YouTube drama",
    "Cold Cases",
    "The Epstein Files",
    "your next vacation",
    "a historical event",
    "your career journey",
    "a personal project",
    "your fitness goals",
    "a book series",
    "a TV show marathon",
    "your education path",
    "a business venture",
    "your home renovation",
    "a music album",
    "a scientific discovery",
    "a political campaign",
    "Fascism",
    "ICE Raids",
    "Science Breakthroughs",
    "Your Weightloss Journey",
    "Your Local Karen"
]
DEFAULT_INTERVAL_MS = 3000
DEFAULT_LED_START_DELAY_SECONDS = 45


def _ensure_site_settings_table(conn):
    conn.execute(text(
        """
        CREATE TABLE IF NOT EXISTS site_settings (
            id SERIAL PRIMARY KEY,
            landing_lead_sentence TEXT NOT NULL DEFAULT '',
            landing_rotator_json TEXT NOT NULL DEFAULT '[]',
            landing_rotation_interval_ms INTEGER NOT NULL DEFAULT 3000,
            landing_rotator_randomize BOOLEAN NOT NULL DEFAULT FALSE,
            landing_badge_text TEXT NOT NULL DEFAULT '',
            landing_badge_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            toolbar_led_message TEXT NOT NULL DEFAULT '',
            toolbar_led_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            toolbar_led_random_start BOOLEAN NOT NULL DEFAULT TRUE,
            toolbar_led_start_delay_seconds INTEGER NOT NULL DEFAULT 45,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    ))
    conn.execute(text(
        """
        ALTER TABLE site_settings
        ADD COLUMN IF NOT EXISTS landing_rotator_randomize BOOLEAN NOT NULL DEFAULT FALSE;
        """
    ))
    conn.execute(text(
        """
        ALTER TABLE site_settings
        ADD COLUMN IF NOT EXISTS landing_badge_text TEXT NOT NULL DEFAULT '';
        """
    ))
    conn.execute(text(
        """
        ALTER TABLE site_settings
        ADD COLUMN IF NOT EXISTS landing_badge_enabled BOOLEAN NOT NULL DEFAULT TRUE;
        """
    ))
    conn.execute(text(
        """
        ALTER TABLE site_settings
        ADD COLUMN IF NOT EXISTS toolbar_led_message TEXT NOT NULL DEFAULT '';
        """
    ))
    conn.execute(text(
        """
        ALTER TABLE site_settings
        ADD COLUMN IF NOT EXISTS toolbar_led_enabled BOOLEAN NOT NULL DEFAULT FALSE;
        """
    ))
    conn.execute(text(
        """
        ALTER TABLE site_settings
        ADD COLUMN IF NOT EXISTS toolbar_led_random_start BOOLEAN NOT NULL DEFAULT TRUE;
        """
    ))
    conn.execute(text(
        """
        ALTER TABLE site_settings
        ADD COLUMN IF NOT EXISTS toolbar_led_start_delay_seconds INTEGER NOT NULL DEFAULT 45;
        """
    ))


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
    except Exception as exc:
        logger.info(f"site_settings: site_admin lookup failed ({exc})")
        return None


def _require_site_owner(conn, user_id):
    try:
        if int(user_id) == 1:
            return True
    except Exception:
        pass
    role = _get_site_admin_role(conn, user_id)
    return role == 'SiteOwner'


def _normalize_endings(raw):
    if not isinstance(raw, list):
        return []
    normalized = []
    for item in raw:
        value = str(item or '').strip()
        if value:
            normalized.append(value)
    return normalized


def _safe_interval(value):
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_MS
    return interval if interval > 0 else DEFAULT_INTERVAL_MS


def _safe_led_start_delay_seconds(value):
    try:
        delay_seconds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LED_START_DELAY_SECONDS
    return delay_seconds if delay_seconds >= 5 else DEFAULT_LED_START_DELAY_SECONDS


def _load_landing_rotator(conn):
    _ensure_site_settings_table(conn)
    row = conn.execute(text(
        """
        SELECT landing_lead_sentence,
               landing_rotator_json,
               landing_rotation_interval_ms,
               landing_rotator_randomize,
               landing_badge_text,
               landing_badge_enabled,
               toolbar_led_message,
               toolbar_led_enabled,
               toolbar_led_random_start,
               toolbar_led_start_delay_seconds
        FROM site_settings
        WHERE id = 1
        """
    )).mappings().first()

    if not row:
        return {
            'lead_sentence': DEFAULT_LEAD_SENTENCE,
            'endings': DEFAULT_ROTATOR,
            'rotation_interval_ms': DEFAULT_INTERVAL_MS,
            'randomize': False,
            'badge_text': 'Not Yet Available, Seeking Funding!',
            'badge_enabled': True,
            'toolbar_led_message': '',
            'toolbar_led_enabled': False,
            'toolbar_led_random_start': True,
            'toolbar_led_start_delay_seconds': DEFAULT_LED_START_DELAY_SECONDS,
        }

    raw_rotator = row.get('landing_rotator_json') or '[]'
    try:
        endings = json.loads(raw_rotator)
    except Exception:
        endings = []

    return {
        'lead_sentence': row.get('landing_lead_sentence') or '',
        'endings': _normalize_endings(endings),
        'rotation_interval_ms': _safe_interval(row.get('landing_rotation_interval_ms')),
        'randomize': bool(row.get('landing_rotator_randomize')),
        'badge_text': row.get('landing_badge_text') or '',
        'badge_enabled': bool(row.get('landing_badge_enabled')),
        'toolbar_led_message': row.get('toolbar_led_message') or '',
        'toolbar_led_enabled': bool(row.get('toolbar_led_enabled')),
        'toolbar_led_random_start': bool(row.get('toolbar_led_random_start')),
        'toolbar_led_start_delay_seconds': _safe_led_start_delay_seconds(row.get('toolbar_led_start_delay_seconds')),
    }


def _save_landing_rotator(
    conn,
    lead_sentence,
    endings,
    interval_ms,
    randomize,
    badge_text,
    badge_enabled,
    toolbar_led_message,
    toolbar_led_enabled,
    toolbar_led_random_start,
    toolbar_led_start_delay_seconds,
):
    _ensure_site_settings_table(conn)
    conn.execute(text(
        """
        INSERT INTO site_settings (
            id,
            landing_lead_sentence,
            landing_rotator_json,
            landing_rotation_interval_ms,
            landing_rotator_randomize,
            landing_badge_text,
            landing_badge_enabled,
            toolbar_led_message,
            toolbar_led_enabled,
            toolbar_led_random_start,
            toolbar_led_start_delay_seconds,
            updated_at
        ) VALUES (
            1,
            :lead_sentence,
            :rotator_json,
            :interval_ms,
            :randomize,
            :badge_text,
            :badge_enabled,
            :toolbar_led_message,
            :toolbar_led_enabled,
            :toolbar_led_random_start,
            :toolbar_led_start_delay_seconds,
            NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
            landing_lead_sentence = EXCLUDED.landing_lead_sentence,
            landing_rotator_json = EXCLUDED.landing_rotator_json,
            landing_rotation_interval_ms = EXCLUDED.landing_rotation_interval_ms,
            landing_rotator_randomize = EXCLUDED.landing_rotator_randomize,
            landing_badge_text = EXCLUDED.landing_badge_text,
            landing_badge_enabled = EXCLUDED.landing_badge_enabled,
            toolbar_led_message = EXCLUDED.toolbar_led_message,
            toolbar_led_enabled = EXCLUDED.toolbar_led_enabled,
            toolbar_led_random_start = EXCLUDED.toolbar_led_random_start,
            toolbar_led_start_delay_seconds = EXCLUDED.toolbar_led_start_delay_seconds,
            updated_at = NOW()
        """
    ), {
        'lead_sentence': lead_sentence,
        'rotator_json': json.dumps(endings),
        'interval_ms': interval_ms,
        'randomize': bool(randomize),
        'badge_text': badge_text,
        'badge_enabled': bool(badge_enabled),
        'toolbar_led_message': toolbar_led_message,
        'toolbar_led_enabled': bool(toolbar_led_enabled),
        'toolbar_led_random_start': bool(toolbar_led_random_start),
        'toolbar_led_start_delay_seconds': _safe_led_start_delay_seconds(toolbar_led_start_delay_seconds),
    })


@site_settings_bp.route('/site-settings/landing-rotator', methods=['GET'])
def get_landing_rotator_settings():
    engine = get_db_engine()
    with engine.begin() as conn:
        landing_rotator = _load_landing_rotator(conn)

    return jsonify({
        'landing_rotator': landing_rotator
    }), 200


@site_settings_bp.route('/site-settings/landing-rotator', methods=['PUT'])
@jwt_required()
def update_landing_rotator_settings():
    data = request.get_json(silent=True) or {}
    lead_sentence = str(data.get('lead_sentence') or '').strip()
    endings = _normalize_endings(data.get('endings'))
    interval_ms = _safe_interval(data.get('rotation_interval_ms'))
    randomize = bool(data.get('randomize'))
    badge_text = str(data.get('badge_text') or '').strip()
    badge_enabled = bool(data.get('badge_enabled'))
    toolbar_led_message = str(data.get('toolbar_led_message') or '').strip()
    toolbar_led_enabled = bool(data.get('toolbar_led_enabled'))
    toolbar_led_random_start = bool(data.get('toolbar_led_random_start'))
    toolbar_led_start_delay_seconds = _safe_led_start_delay_seconds(data.get('toolbar_led_start_delay_seconds'))

    engine = get_db_engine()
    with engine.begin() as conn:
        if not _require_site_owner(conn, get_jwt_identity()):
            return jsonify({'error': 'Access denied'}), 403

        _save_landing_rotator(
            conn,
            lead_sentence,
            endings,
            interval_ms,
            randomize,
            badge_text,
            badge_enabled,
            toolbar_led_message,
            toolbar_led_enabled,
            toolbar_led_random_start,
            toolbar_led_start_delay_seconds,
        )
        landing_rotator = _load_landing_rotator(conn)

    return jsonify({
        'message': 'Landing rotator settings updated',
        'landing_rotator': landing_rotator
    }), 200
