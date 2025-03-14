import sqlite3
import os

def add_image_to_posts():
    # Get the database path
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'timeline_forum.db')
    
    # Create the instance directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check if image column exists
    c.execute("PRAGMA table_info(post)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'image' not in columns:
        # Add image column to posts table
        c.execute('''
            ALTER TABLE post
            ADD COLUMN image TEXT
        ''')
        
        conn.commit()
        print("Added image column to posts table")
    else:
        print("Image column already exists in posts table")
    
    conn.close()

if __name__ == '__main__':
    add_image_to_posts()
