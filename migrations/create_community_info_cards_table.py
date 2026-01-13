"""
Migration: Create community_info_card table for Community Info Cards feature
Date: 2026-01-12

This migration creates the community_info_card table to store informational cards
that moderators and admins can create for their community timelines.

Uses CREATE TABLE IF NOT EXISTS to safely add the table without affecting existing data.
"""

from sqlalchemy import text as _sql_text
from app import db, app

def create_community_info_cards_table():
    """Create the community_info_card table if it does not exist (PostgreSQL)."""
    try:
        db.session.execute(_sql_text(
            """
            CREATE TABLE IF NOT EXISTS community_info_card (
                id SERIAL PRIMARY KEY,
                timeline_id INTEGER NOT NULL REFERENCES timeline(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                card_order INTEGER DEFAULT 0,
                created_by INTEGER NOT NULL REFERENCES "user"(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(timeline_id, title)
            )
            """
        ))
        db.session.commit()
        app.logger.info("✅ community_info_card table created successfully")
        return True
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"❌ Failed to create community_info_card table: {e}")
        return False

def create_index():
    """Create indexes for better query performance."""
    try:
        db.session.execute(_sql_text(
            """
            CREATE INDEX IF NOT EXISTS idx_community_info_card_timeline_id 
            ON community_info_card(timeline_id)
            """
        ))
        db.session.execute(_sql_text(
            """
            CREATE INDEX IF NOT EXISTS idx_community_info_card_created_by 
            ON community_info_card(created_by)
            """
        ))
        db.session.commit()
        app.logger.info("✅ Indexes created successfully")
        return True
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"❌ Failed to create indexes: {e}")
        return False

if __name__ == '__main__':
    with app.app_context():
        print("Running migration: create_community_info_cards_table")
        if create_community_info_cards_table():
            if create_index():
                print("✅ Migration completed successfully")
            else:
                print("⚠️ Table created but index creation failed")
        else:
            print("❌ Migration failed")
