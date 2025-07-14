import re
import os
import shutil

def fix_app_db_path():
    """
    Update the database path in app.py to point to the correct location.
    """
    try:
        print("Backing up app.py...")
        # Create a backup of the original file
        shutil.copy2('app.py', 'app.py.bak')
        print("Backup created as app.py.bak")
        
        print("\nUpdating database path in app.py...")
        # Read the app.py file
        with open('app.py', 'r') as file:
            content = file.read()
        
        # Update the database URI
        updated_content = re.sub(
            r"SQLALCHEMY_DATABASE_URI='sqlite:///timeline_forum.db'",
            "SQLALCHEMY_DATABASE_URI='sqlite:///instance/timeline_forum.db'",
            content
        )
        
        # Write the updated content back to app.py
        with open('app.py', 'w') as file:
            file.write(updated_content)
        
        print("Successfully updated database path in app.py")
        print("The application will now use 'instance/timeline_forum.db' instead of 'timeline_forum.db'")
        
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the join button functionality")
        print("3. Verify that membership status persists after logout and login")
        
    except Exception as e:
        print(f"Error updating app.py: {str(e)}")

if __name__ == "__main__":
    fix_app_db_path()
