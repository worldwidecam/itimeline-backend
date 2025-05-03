"""
Run the iTimeline backend with OpenAPI documentation enabled.

This script runs the OpenAPI-enhanced version of the iTimeline backend,
which provides interactive API documentation through Swagger UI.
"""

from api_docs import app

if __name__ == "__main__":
    # Run the OpenAPI-wrapped version of the app
    print("Starting iTimeline API with OpenAPI documentation...")
    print("API documentation available at: http://localhost:5000/openapi")
    print("Interactive Swagger UI available at: http://localhost:5000/swagger-ui")
    app.run(host='0.0.0.0', port=5000, debug=True)
