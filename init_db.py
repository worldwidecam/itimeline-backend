from app import app, db

with app.app_context():
    db.drop_all()  # Drop all existing tables
    db.create_all()  # Create new tables with updated schema
    print("Database initialized successfully!")
