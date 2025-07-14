import os
import shutil
import re

def register_passport_blueprint():
    """
    Register the passport blueprint in app.py to ensure the user passport endpoints are accessible.
    """
    try:
        print("Backing up app.py...")
        # Create a backup of the original file
        shutil.copy2('app.py', 'app.py.blueprint.bak')
        print("Backup created as app.py.blueprint.bak")
        
        print("\nRegistering passport blueprint in app.py...")
        # Read the app.py file
        with open('app.py', 'r') as file:
            content = file.read()
        
        # Check if the passport blueprint is already imported
        if "from routes.passport import passport_bp" not in content:
            # Add the import statement after other blueprint imports
            content = re.sub(
                r"(from flask_cors import CORS.*?\n)",
                r"\1from routes.passport import passport_bp\n",
                content,
                flags=re.DOTALL
            )
        
        # Check if the blueprint is already registered
        if "app.register_blueprint(passport_bp, url_prefix='/api/v1')" not in content:
            # Add the blueprint registration after CORS configuration
            content = re.sub(
                r"(supports_credentials=True\).*?\n)",
                r"\1\n# Register passport blueprint\napp.register_blueprint(passport_bp, url_prefix='/api/v1')\nprint(\"Registered passport blueprint with url_prefix='/api/v1'\")\n",
                content,
                flags=re.DOTALL
            )
        
        # Write the updated content back to app.py
        with open('app.py', 'w') as file:
            file.write(content)
        
        print("Successfully registered passport blueprint in app.py")
        print("The user passport endpoints should now be accessible at /api/v1/user/passport and /api/v1/user/passport/sync")
        
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the join button functionality")
        print("3. Verify that membership status persists after logout and login")
        
    except Exception as e:
        print(f"Error registering passport blueprint: {str(e)}")

if __name__ == "__main__":
    register_passport_blueprint()
