
from flask import Flask, request, jsonify, make_response

def add_cors_headers(app):
    """
    Add CORS headers to all responses using Flask's after_request handler.
    This ensures that all routes, including those in blueprints, have proper CORS headers.
    """
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
