from app import app, db, User, Timeline
from werkzeug.security import generate_password_hash

def create_test_data():
    with app.app_context():
        # Create test user if it doesn't exist
        if not User.query.filter_by(email='test@example.com').first():
            test_user = User(
                username='testuser',
                email='test@example.com',
                password_hash=generate_password_hash('password123')
            )
            db.session.add(test_user)
            
            # Create default timeline
            if not Timeline.query.filter_by(name='General').first():
                general_timeline = Timeline(
                    name='General',
                    description='General timeline for uncategorized posts',
                    created_by=1
                )
                db.session.add(general_timeline)
            
            db.session.commit()
            print("Test user and default timeline created successfully!")
        else:
            print("Test user already exists!")

if __name__ == '__main__':
    create_test_data()
