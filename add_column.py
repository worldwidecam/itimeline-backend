from app import app, db
from sqlalchemy import Column, String, text

with app.app_context():
    # Check if the column exists
    try:
        # Try to add the column if it doesn't exist
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE event ADD COLUMN raw_event_date VARCHAR(100)"))
            conn.commit()
        print("Column 'raw_event_date' added successfully")
    except Exception as e:
        print(f"Error adding column (it may already exist): {str(e)}")
