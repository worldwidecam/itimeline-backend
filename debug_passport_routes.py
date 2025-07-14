import os
import sqlite3
import json
from datetime import datetime

def debug_passport_routes():
    """
    Debug the user passport routes by directly examining the database and route files.
    """
    print("Debugging User Passport Routes")
    print("==============================\n")
    
    # Check if the passport blueprint is imported in app.py
    print("Step 1: Checking if passport blueprint is imported in app.py...")
    with open('app.py', 'r') as file:
        app_content = file.read()
    
    if "from routes.passport import passport_bp" in app_content:
        print("✓ Passport blueprint is imported in app.py")
    else:
        print("✗ Passport blueprint is NOT imported in app.py")
    
    if "app.register_blueprint(passport_bp" in app_content:
        print("✓ Passport blueprint is registered in app.py")
    else:
        print("✗ Passport blueprint is NOT registered in app.py")
    
    # Check if the sqlite3 module is imported in passport.py
    print("\nStep 2: Checking if sqlite3 is imported in passport.py...")
    try:
        with open('routes/passport.py', 'r') as file:
            passport_content = file.read()
        
        if "import sqlite3" in passport_content:
            print("✓ sqlite3 module is imported in passport.py")
        else:
            print("✗ sqlite3 module is NOT imported in passport.py")
    except Exception as e:
        print(f"✗ Error reading passport.py: {str(e)}")
    
    # Check if the user_passport table exists in the database
    print("\nStep 3: Checking if user_passport table exists in the database...")
    try:
        # Check in instance/timeline_forum.db
        instance_db_path = 'instance/timeline_forum.db'
        if os.path.exists(instance_db_path):
            conn = sqlite3.connect(instance_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
            if cursor.fetchone():
                print(f"✓ user_passport table exists in {instance_db_path}")
                
                # Check if there are records in the table
                cursor.execute("SELECT COUNT(*) FROM user_passport")
                count = cursor.fetchone()[0]
                print(f"  - Found {count} records in user_passport table")
                
                # Show a sample record if available
                if count > 0:
                    cursor.execute("SELECT * FROM user_passport LIMIT 1")
                    columns = [description[0] for description in cursor.description]
                    record = cursor.fetchone()
                    record_dict = dict(zip(columns, record))
                    print(f"  - Sample record: {json.dumps(record_dict, default=str, indent=2)}")
            else:
                print(f"✗ user_passport table does NOT exist in {instance_db_path}")
            conn.close()
        else:
            print(f"✗ Database file {instance_db_path} does not exist")
        
        # Check in root timeline_forum.db
        root_db_path = 'timeline_forum.db'
        if os.path.exists(root_db_path):
            conn = sqlite3.connect(root_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_passport'")
            if cursor.fetchone():
                print(f"✓ user_passport table exists in {root_db_path}")
                
                # Check if there are records in the table
                cursor.execute("SELECT COUNT(*) FROM user_passport")
                count = cursor.fetchone()[0]
                print(f"  - Found {count} records in user_passport table")
                
                # Show a sample record if available
                if count > 0:
                    cursor.execute("SELECT * FROM user_passport LIMIT 1")
                    columns = [description[0] for description in cursor.description]
                    record = cursor.fetchone()
                    record_dict = dict(zip(columns, record))
                    print(f"  - Sample record: {json.dumps(record_dict, default=str, indent=2)}")
            else:
                print(f"✗ user_passport table does NOT exist in {root_db_path}")
            conn.close()
        else:
            print(f"✗ Database file {root_db_path} does not exist")
    except Exception as e:
        print(f"✗ Error checking database: {str(e)}")
    
    print("\nDebugging complete!")

if __name__ == "__main__":
    debug_passport_routes()
