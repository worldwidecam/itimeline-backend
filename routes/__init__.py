"""
Blueprint registration module for the iTimeline backend.
This centralizes all blueprint registrations to avoid circular imports and ensure consistent URL prefixes.
"""

from flask import Flask

def register_passport_blueprint(app: Flask):
    """
    Register the passport blueprint with the Flask app.
    
    Args:
        app: The Flask application instance
    """
    # Import passport blueprint
    from routes.passport import passport_bp
    
    # Register passport blueprint with appropriate URL prefix
    app.register_blueprint(passport_bp, url_prefix='/api/v1')
    
    print("Passport blueprint registered successfully")
