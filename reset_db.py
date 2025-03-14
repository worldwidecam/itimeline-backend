from app import app, db

with app.app_context():
    # Drop all tables
    print("Dropping all tables...")
    db.drop_all()
    
    # Recreate all tables with current schema
    print("Creating tables with current schema...")
    db.create_all()
    
    # Create a default user (id=1) for our development
    from app import User
    default_user = User(
        id=1,
        username='dev_user',
        email='dev@example.com'
    )
    default_user.set_password('password')
    
    try:
        db.session.add(default_user)
        db.session.commit()
        print("Created default user (id=1)")
    except Exception as e:
        print(f"Note: Default user already exists or {str(e)}")
    
    print("Database reset complete!")
