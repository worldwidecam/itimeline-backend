import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
import json

# Delete existing database if it exists
if os.path.exists('timeline_forum.db'):
    print("Removing existing database...")
    os.remove('timeline_forum.db')

# Connect to a new database
conn = sqlite3.connect('timeline_forum.db')
cursor = conn.cursor()

print("Creating database schema...")

# Create user table
cursor.execute('''
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bio TEXT,
    avatar_url TEXT
)
''')

# Create timeline table
cursor.execute('''
CREATE TABLE timeline (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timeline_type TEXT DEFAULT 'hashtag' NOT NULL,
    visibility TEXT DEFAULT 'public' NOT NULL,
    privacy_changed_at TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES user (id)
)
''')

# Create timeline_member table with is_active_member column
cursor.execute('''
CREATE TABLE timeline_member (
    id INTEGER PRIMARY KEY,
    timeline_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    is_active_member BOOLEAN DEFAULT TRUE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    invited_by INTEGER,
    FOREIGN KEY (timeline_id) REFERENCES timeline (id),
    FOREIGN KEY (user_id) REFERENCES user (id),
    FOREIGN KEY (invited_by) REFERENCES user (id),
    UNIQUE (timeline_id, user_id)
)
''')

# Create event table
cursor.execute('''
CREATE TABLE event (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    event_date TIMESTAMP NOT NULL,
    raw_event_date TEXT DEFAULT '',
    type TEXT DEFAULT 'remark' NOT NULL,
    url TEXT,
    url_title TEXT,
    url_description TEXT,
    url_image TEXT,
    media_url TEXT,
    media_type TEXT,
    media_subtype TEXT,
    cloudinary_id TEXT,
    timeline_id INTEGER NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_exact_user_time BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (timeline_id) REFERENCES timeline (id),
    FOREIGN KEY (created_by) REFERENCES user (id)
)
''')

# Create tag table
cursor.execute('''
CREATE TABLE tag (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timeline_id INTEGER,
    FOREIGN KEY (timeline_id) REFERENCES timeline (id)
)
''')

# Create event_tags table
cursor.execute('''
CREATE TABLE event_tags (
    event_id INTEGER,
    tag_id INTEGER,
    PRIMARY KEY (event_id, tag_id),
    FOREIGN KEY (event_id) REFERENCES event (id),
    FOREIGN KEY (tag_id) REFERENCES tag (id)
)
''')

# Create event_timeline_refs table
cursor.execute('''
CREATE TABLE event_timeline_refs (
    event_id INTEGER,
    timeline_id INTEGER,
    PRIMARY KEY (event_id, timeline_id),
    FOREIGN KEY (event_id) REFERENCES event (id),
    FOREIGN KEY (timeline_id) REFERENCES timeline (id)
)
''')

# Create event_timeline_association table
cursor.execute('''
CREATE TABLE event_timeline_association (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL,
    timeline_id INTEGER NOT NULL,
    shared_by INTEGER NOT NULL,
    shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_timeline_id INTEGER,
    FOREIGN KEY (event_id) REFERENCES event (id),
    FOREIGN KEY (timeline_id) REFERENCES timeline (id),
    FOREIGN KEY (shared_by) REFERENCES user (id),
    FOREIGN KEY (source_timeline_id) REFERENCES timeline (id),
    UNIQUE (event_id, timeline_id)
)
''')

# Create post table
cursor.execute('''
CREATE TABLE post (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    event_date TIMESTAMP NOT NULL,
    url TEXT,
    url_title TEXT,
    url_description TEXT,
    url_image TEXT,
    image TEXT,
    timeline_id INTEGER,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    upvotes INTEGER DEFAULT 0,
    promoted_to_event BOOLEAN DEFAULT FALSE,
    promotion_score FLOAT DEFAULT 0.0,
    source_count INTEGER DEFAULT 0,
    promotion_votes INTEGER DEFAULT 0,
    FOREIGN KEY (timeline_id) REFERENCES timeline (id),
    FOREIGN KEY (created_by) REFERENCES user (id)
)
''')

# Create comment table
cursor.execute('''
CREATE TABLE comment (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    post_id INTEGER,
    user_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES post (id),
    FOREIGN KEY (user_id) REFERENCES user (id)
)
''')

# Create token_blocklist table
cursor.execute('''
CREATE TABLE token_blocklist (
    id INTEGER PRIMARY KEY,
    jti TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user (id)
)
''')

# Create user_music table
cursor.execute('''
CREATE TABLE user_music (
    id INTEGER PRIMARY KEY,
    user_id INTEGER UNIQUE,
    music_url TEXT,
    music_platform TEXT,
    music_public_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user (id)
)
''')

print("Creating test users...")

# Insert test users
users = [
    (1, 'SiteOwner', 'admin@example.com', generate_password_hash('password'), datetime.now(), 'Site administrator', None),
    (2, 'TestUser1', 'user1@example.com', generate_password_hash('password'), datetime.now(), 'Regular user', None),
    (3, 'TestUser2', 'user2@example.com', generate_password_hash('password'), datetime.now(), 'Another user', None),
    (4, 'TestUser3', 'user3@example.com', generate_password_hash('password'), datetime.now(), 'Third user', None)
]

cursor.executemany('''
INSERT INTO user (id, username, email, password_hash, created_at, bio, avatar_url)
VALUES (?, ?, ?, ?, ?, ?, ?)
''', users)

print("Creating test timelines...")

# Insert test timelines
timelines = [
    (1, 'Technology', 'Timeline about technology', 2, datetime.now(), 'hashtag', 'public', None),
    (2, 'Science', 'Timeline about science', 3, datetime.now(), 'hashtag', 'public', None),
    (3, 'Community Tech', 'A community for tech enthusiasts', 2, datetime.now(), 'community', 'public', None),
    (4, 'Private Community', 'A private community', 3, datetime.now(), 'community', 'private', datetime.now())
]

cursor.executemany('''
INSERT INTO timeline (id, name, description, created_by, created_at, timeline_type, visibility, privacy_changed_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
''', timelines)

print("Creating timeline members...")

# Insert timeline members
members = [
    (1, 3, 2, 'admin', True, datetime.now(), None),  # TestUser1 is admin of Community Tech (creator)
    (2, 3, 3, 'member', True, datetime.now(), 2),    # TestUser2 is member of Community Tech
    (3, 4, 3, 'admin', True, datetime.now(), None),  # TestUser2 is admin of Private Community (creator)
    (4, 4, 1, 'member', True, datetime.now(), 3),    # SiteOwner is member of Private Community
    # TestUser3 is not a member of any community
]

cursor.executemany('''
INSERT INTO timeline_member (id, timeline_id, user_id, role, is_active_member, joined_at, invited_by)
VALUES (?, ?, ?, ?, ?, ?, ?)
''', members)

print("Creating test events...")

# Insert test events
events = [
    (1, 'First Technology Event', 'Description for first tech event', datetime.now() - timedelta(days=10), 
     '10 days ago', 'remark', 'https://example.com', 'Example URL', 'URL description', None, 
     None, None, None, None, 1, 2, datetime.now() - timedelta(days=10), datetime.now() - timedelta(days=10), False),
    
    (2, 'First Science Event', 'Description for first science event', datetime.now() - timedelta(days=5), 
     '5 days ago', 'remark', 'https://example.com', 'Example URL', 'URL description', None, 
     None, None, None, None, 2, 3, datetime.now() - timedelta(days=5), datetime.now() - timedelta(days=5), False),
    
    (3, 'Community Tech Event', 'Description for community tech event', datetime.now() - timedelta(days=3), 
     '3 days ago', 'remark', 'https://example.com', 'Example URL', 'URL description', None, 
     None, None, None, None, 3, 2, datetime.now() - timedelta(days=3), datetime.now() - timedelta(days=3), False),
    
    (4, 'Private Community Event', 'Description for private community event', datetime.now() - timedelta(days=1), 
     'yesterday', 'remark', 'https://example.com', 'Example URL', 'URL description', None, 
     None, None, None, None, 4, 3, datetime.now() - timedelta(days=1), datetime.now() - timedelta(days=1), False)
]

cursor.executemany('''
INSERT INTO event (id, title, description, event_date, raw_event_date, type, url, url_title, url_description, 
                  url_image, media_url, media_type, media_subtype, cloudinary_id, timeline_id, created_by, 
                  created_at, updated_at, is_exact_user_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', events)

# Commit changes and close connection
conn.commit()
conn.close()

print("Database initialization complete!")
print("Test data summary:")
print("- 4 users created (including SiteOwner)")
print("- 2 hashtag timelines created")
print("- 2 community timelines created (1 public, 1 private)")
print("- 4 timeline members created")
print("- 4 events created (1 for each timeline)")
print("\nYou can now test the membership system with these users:")
print("1. SiteOwner (ID: 1) - Should have access to all timelines")
print("2. TestUser1 (ID: 2) - Creator and admin of 'Community Tech'")
print("3. TestUser2 (ID: 3) - Member of 'Community Tech', creator and admin of 'Private Community'")
print("4. TestUser3 (ID: 4) - Not a member of any community")
