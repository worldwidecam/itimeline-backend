#!/usr/bin/env python3
"""
Migration script to create the user_passport table in the database.
This table stores persistent membership data for users across devices.
"""

import sqlite3
import json
from datetime import datetime

# Connect to the database
conn = sqlite3.connect('timeline_forum.db')
cursor = conn.cursor()

# Check if the table already exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
if cursor.fetchone():
    print("Table 'user_passport' already exists.")
else:
    # Create the user_passport table
    cursor.execute('''
    CREATE TABLE user_passport (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        memberships_json TEXT NOT NULL DEFAULT '[]',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES user(id)
    )
    ''')
    
    print("Created 'user_passport' table.")
    
    # Create an index on user_id for faster lookups
    cursor.execute('CREATE INDEX idx_user_passport_user_id ON user_passport(user_id)')
    print("Created index on user_id.")
    
    # Initialize passports for all existing users
    cursor.execute('SELECT id FROM user')
    users = cursor.fetchall()
    
    for user in users:
        user_id = user[0]
        # Create empty passport for each user
        cursor.execute(
            'INSERT INTO user_passport (user_id, memberships_json, last_updated) VALUES (?, ?, ?)',
            (user_id, '[]', datetime.now())
        )
        print(f"Created passport for user ID: {user_id}")

# Commit changes and close connection
conn.commit()
conn.close()

print("Migration completed successfully.")
