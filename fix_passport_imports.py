import os
import shutil
import re

def fix_passport_imports():
    """
    Fix the missing sqlite3 import in the passport routes.
    """
    try:
        print("Backing up routes/passport.py...")
        # Create a backup of the original file
        shutil.copy2('routes/passport.py', 'routes/passport.py.import.bak')
        print("Backup created as routes/passport.py.import.bak")
        
        print("\nUpdating imports in routes/passport.py...")
        # Read the file
        with open('routes/passport.py', 'r') as file:
            content = file.read()
        
        # Check if sqlite3 is already imported
        if 'import sqlite3' not in content:
            # Add the import statement after other imports
            content = re.sub(
                r"(import logging.*?\n)",
                r"\1import sqlite3\n",
                content,
                flags=re.DOTALL
            )
        
        # Write the updated content back to the file
        with open('routes/passport.py', 'w') as file:
            file.write(content)
        
        print("Successfully added sqlite3 import to routes/passport.py")
        
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the user passport endpoints")
        
    except Exception as e:
        print(f"Error updating imports: {str(e)}")

if __name__ == "__main__":
    fix_passport_imports()
