from app import db
from datetime import datetime

def upgrade():
    # Add display_type column to posts table
    db.engine.execute('''
        ALTER TABLE post 
        ADD COLUMN display_type VARCHAR(20) DEFAULT 'feed' NOT NULL
    ''')

    # Migrate events to posts
    db.engine.execute('''
        INSERT INTO post (
            title, content, event_date, url, url_title, 
            url_description, url_image, timeline_id, 
            created_by, created_at, upvotes, display_type
        )
        SELECT 
            title, content, event_date, url, url_title,
            url_description, url_image, timeline_id,
            created_by, created_at, upvotes, 'timeline'
        FROM event
    ''')

    # Move comments from events to posts
    db.engine.execute('''
        UPDATE comment
        SET post_id = (
            SELECT p.id 
            FROM post p 
            JOIN event e ON p.title = e.title 
                AND p.created_at = e.created_at
                AND p.timeline_id = e.timeline_id
            WHERE e.id = comment.event_id
        )
        WHERE event_id IS NOT NULL
    ''')

    # Drop the events table
    db.engine.execute('DROP TABLE event')

def downgrade():
    # Create events table
    db.engine.execute('''
        CREATE TABLE event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            content TEXT,
            event_date DATETIME NOT NULL,
            url VARCHAR(500),
            url_title VARCHAR(500),
            url_description TEXT,
            url_image VARCHAR(500),
            timeline_id INTEGER REFERENCES timeline(id),
            created_by INTEGER REFERENCES user(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            upvotes INTEGER DEFAULT 0
        )
    ''')

    # Move timeline posts back to events
    db.engine.execute('''
        INSERT INTO event (
            title, content, event_date, url, url_title,
            url_description, url_image, timeline_id,
            created_by, created_at, upvotes
        )
        SELECT 
            title, content, event_date, url, url_title,
            url_description, url_image, timeline_id,
            created_by, created_at, upvotes
        FROM post
        WHERE display_type = 'timeline'
    ''')

    # Remove display_type column from posts
    db.engine.execute('ALTER TABLE post DROP COLUMN display_type')
