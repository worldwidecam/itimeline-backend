from app import app, db
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Boolean, text

# Run this script to add the is_exact_user_time column to the Event table
# This is a simple migration script since we don't have a formal migration system

def add_exact_time_column():
    with app.app_context():
        # Check if the column already exists
        inspector = db.inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('event')]
        
        if 'is_exact_user_time' not in columns:
            print("Adding is_exact_user_time column to Event table...")
            # Add the column using the correct SQLAlchemy API
            with db.engine.connect() as conn:
                conn.execute(text('ALTER TABLE event ADD COLUMN is_exact_user_time BOOLEAN DEFAULT FALSE'))
                conn.commit()
            print("Column added successfully!")
        else:
            print("Column is_exact_user_time already exists.")

if __name__ == '__main__':
    add_exact_time_column()
