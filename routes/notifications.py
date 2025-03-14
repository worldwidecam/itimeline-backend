from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import sqlite3
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)

def get_db_connection():
    conn = sqlite3.connect('instance/timeline.db')
    conn.row_factory = sqlite3.Row
    return conn

@notifications_bp.route('/api/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    current_user_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, message, type, reference_id, read, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
    ''', (current_user_id,))
    
    notifications = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(notifications)

@notifications_bp.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@jwt_required()
def mark_notification_read(notification_id):
    current_user_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE notifications
        SET read = 1
        WHERE id = ? AND user_id = ?
    ''', (notification_id, current_user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Notification marked as read'})

def create_notification(user_id, message, notification_type, reference_id=None):
    """Utility function to create a new notification"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO notifications (user_id, message, type, reference_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, message, notification_type, reference_id))
    
    notification_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return notification_id
