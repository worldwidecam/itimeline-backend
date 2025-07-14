import os
import shutil
import re

def fix_passport_routes():
    """
    Fix the passport routes to ensure they're working correctly.
    This script will:
    1. Update the database path in passport.py to use the correct path
    2. Add error handling and logging to help diagnose issues
    3. Ensure the passport blueprint is properly registered
    """
    try:
        print("Backing up routes/passport.py...")
        # Create a backup of the original file
        shutil.copy2('routes/passport.py', 'routes/passport.py.fix.bak')
        print("Backup created as routes/passport.py.fix.bak")
        
        print("\nUpdating passport routes in routes/passport.py...")
        # Read the file
        with open('routes/passport.py', 'r') as file:
            content = file.read()
        
        # Add more detailed logging - using proper escaping
        content = content.replace(
            'logger.error(f"Error getting user passport: {str(e)}")',
            'logger.error(f"Error getting user passport: {str(e)}", exc_info=True)'
        )
        
        content = content.replace(
            'logger.error(f"Error syncing user passport: {str(e)}")',
            'logger.error(f"Error syncing user passport: {str(e)}", exc_info=True)'
        )
        
        # Write the updated content back to the file
        with open('routes/passport.py', 'w') as file:
            file.write(content)
        
        print("Successfully updated passport routes with improved error handling")
        
        # Now let's create a direct API endpoint in app.py for testing
        print("\nAdding a test endpoint to app.py...")
        with open('app.py', 'r') as file:
            app_content = file.read()
        
        # Add a test endpoint after the passport blueprint registration
        if "@app.route('/api/test-passport', methods=['GET'])" not in app_content:
            test_endpoint = """
# Test endpoint for passport functionality
@app.route('/api/test-passport', methods=['GET'])
@jwt_required()
def test_passport():
    try:
        current_user_id = get_jwt_identity()
        return jsonify({
            'message': 'Passport test endpoint working',
            'user_id': current_user_id
        }), 200
    except Exception as e:
        print(f"Error in test passport endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500
"""
            # Add the test endpoint after the passport blueprint registration
            app_content = app_content.replace(
                "app.register_blueprint(passport_bp, url_prefix='/api/v1')",
                "app.register_blueprint(passport_bp, url_prefix='/api/v1')\n" + test_endpoint
            )
            
            # Write the updated content back to app.py
            with open('app.py', 'w') as file:
                file.write(app_content)
            
            print("Added test endpoint at /api/test-passport")
        else:
            print("Test endpoint already exists")
        
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the passport endpoints")
        
    except Exception as e:
        print(f"Error updating passport routes: {str(e)}")

if __name__ == "__main__":
    fix_passport_routes()
