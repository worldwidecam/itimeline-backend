"""
Fix CORS issues for passport endpoints by ensuring all API responses have proper CORS headers.
"""
import os
import shutil

def fix_cors_for_passport():
    """
    Update the CORS configuration in app.py to ensure all API responses have proper CORS headers.
    This should help resolve issues with the frontend accessing the passport endpoints.
    """
    print("Fixing CORS configuration for passport endpoints...")
    
    # Backup app.py before making changes
    backup_path = 'app.py.cors.bak'
    shutil.copy2('app.py', backup_path)
    print(f"Created backup of app.py at {backup_path}")
    
    # Read the current app.py content
    with open('app.py', 'r') as file:
        content = file.read()
    
    # Check if we already have the updated CORS configuration
    if "CORS(app, resources={r'/*': {'origins': '*'}})" in content:
        print("CORS already configured to allow all origins")
    else:
        # Update CORS configuration to allow all origins
        updated_content = content.replace(
            "CORS(app, origins=allowed_origins, supports_credentials=True)",
            "CORS(app, resources={r'/*': {'origins': '*'}}, supports_credentials=True)"
        )
        
        # Write the updated content back to app.py
        with open('app.py', 'w') as file:
            file.write(updated_content)
        print("Updated CORS configuration to allow all origins")
    
    # Check if we already have the after_request handler
    if "@app.after_request\ndef after_request(response):" in content:
        print("after_request handler already exists")
    else:
        # Add an after_request handler to ensure CORS headers are included on all responses
        after_request_handler = """
# Add CORS headers to all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response
"""
        # Find a good place to insert the after_request handler (before the app.run line)
        if "if __name__ == '__main__':" in content:
            updated_content = content.replace(
                "if __name__ == '__main__':",
                after_request_handler + "\nif __name__ == '__main__':"
            )
            
            # Write the updated content back to app.py
            with open('app.py', 'w') as file:
                file.write(updated_content)
            print("Added after_request handler to ensure CORS headers are included on all responses")
    
    print("\nCORS configuration updated successfully!")
    print("Please restart the Flask server for the changes to take effect.")

if __name__ == "__main__":
    fix_cors_for_passport()
