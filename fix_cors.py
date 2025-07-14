import os
import shutil
import re

def fix_cors_configuration():
    """
    Fix the CORS configuration in app.py to ensure it properly handles all routes,
    especially the passport and community endpoints.
    """
    try:
        print("Backing up app.py...")
        # Create a backup of the original file
        shutil.copy2('app.py', 'app.py.cors.bak')
        print("Backup created as app.py.cors.bak")
        
        print("\nUpdating CORS configuration in app.py...")
        # Read the app.py file
        with open('app.py', 'r') as file:
            content = file.read()
        
        # Update the CORS configuration to be more permissive
        cors_pattern = r"CORS\(app, resources=\{.*?\}, supports_credentials=True\)"
        new_cors_config = """CORS(app, 
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    expose_headers=["Content-Type", "Authorization"]
)"""
        
        # Replace the CORS configuration
        updated_content = re.sub(cors_pattern, new_cors_config, content, flags=re.DOTALL)
        
        # Add CORS handling after each blueprint registration
        blueprint_pattern = r"(app\.register_blueprint\(.*?\))"
        updated_content = re.sub(blueprint_pattern, r"\1\n# Ensure CORS is applied to this blueprint", updated_content)
        
        # Write the updated content back to app.py
        with open('app.py', 'w') as file:
            file.write(updated_content)
        
        # Now create a separate file to add CORS headers to all responses
        print("\nCreating a CORS after_request handler...")
        with open('cors_handler.py', 'w') as file:
            file.write("""
from flask import Flask, request, jsonify, make_response

def add_cors_headers(app):
    \"\"\"
    Add CORS headers to all responses using Flask's after_request handler.
    This ensures that all routes, including those in blueprints, have proper CORS headers.
    \"\"\"
    @app.after_request
    def add_cors_headers_to_response(response):
        # Allow requests from any origin
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, X-Requested-With'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        
        # Handle preflight OPTIONS requests
        if request.method == 'OPTIONS':
            return make_response('', 200)
            
        return response
    
    print("Added CORS headers to all responses via after_request handler")
    return app
""")
        
        # Now update app.py to use the CORS handler
        print("\nUpdating app.py to use the CORS handler...")
        with open('app.py', 'r') as file:
            content = file.read()
        
        # Add import for the CORS handler
        import_pattern = r"from flask_cors import CORS"
        updated_content = re.sub(import_pattern, r"from flask_cors import CORS\nfrom cors_handler import add_cors_headers", content)
        
        # Add the CORS handler after the CORS configuration
        cors_config_pattern = r"(CORS\(app.*?\)\n)"
        updated_content = re.sub(cors_config_pattern, r"\1\n# Add CORS headers to all responses\napp = add_cors_headers(app)\n", updated_content, flags=re.DOTALL)
        
        # Write the updated content back to app.py
        with open('app.py', 'w') as file:
            file.write(updated_content)
        
        print("\nCORS configuration has been updated.")
        print("The application will now properly handle CORS for all routes, including passport and community endpoints.")
        
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the join button functionality again")
        
    except Exception as e:
        print(f"Error updating CORS configuration: {str(e)}")

if __name__ == "__main__":
    fix_cors_configuration()
