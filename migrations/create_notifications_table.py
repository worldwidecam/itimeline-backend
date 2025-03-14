from flask import current_app
import sqlite3

def create_notifications_table():
    with current_app.app_context():
        conn = sqlite3.connect('instance/timeline.db')
        c = conn.cursor()
        
        # Create notifications table
        c.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                type TEXT NOT NULL,
                reference_id INTEGER,
                read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create index for faster queries
        c.execute('''
            CREATE INDEX IF NOT EXISTS idx_notifications_user
            ON notifications (user_id, read)
        ''')
        
        conn.commit()
        conn.close()

if __name__ == '__main__':
    create_notifications_table()
