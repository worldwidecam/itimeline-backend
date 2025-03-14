import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db

def init_tags():
    with app.app_context():
        # Create new tables
        db.create_all()
        
        print("Tag system initialized successfully!")

if __name__ == '__main__':
    init_tags()
