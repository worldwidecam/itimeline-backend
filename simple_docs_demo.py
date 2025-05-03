"""
Simple API Documentation Demo for iTimeline

This is a standalone example that shows how API documentation works.
It creates a mini version of your API with documentation to demonstrate the concept.
"""

from flask import Flask, jsonify, request
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask_apispec.extension import FlaskApiSpec
from flask_apispec import use_kwargs, marshal_with, doc
from marshmallow import Schema, fields
import datetime

# Create a simple Flask app
app = Flask(__name__)

# Set up API documentation
app.config.update({
    'APISPEC_SPEC': APISpec(
        title='iTimeline API',
        version='1.0.0',
        openapi_version='2.0',  # Using 2.0 for better compatibility
        plugins=[MarshmallowPlugin()],
        info={
            'description': 'API for the iTimeline application',
            'contact': {'email': 'support@i-timeline.com'},
        },
    ),
    'APISPEC_SWAGGER_URL': '/openapi',  # Where to get the OpenAPI JSON
    'APISPEC_SWAGGER_UI_URL': '/swagger-ui',  # Where to get the UI
})

docs = FlaskApiSpec(app)

# Define some simple schemas
class UserSchema(Schema):
    id = fields.Int(description="User ID")
    username = fields.Str(description="Username")
    email = fields.Str(description="Email address")

class LoginSchema(Schema):
    email = fields.Str(required=True, description="Email address")
    password = fields.Str(required=True, description="Password")

class TokenSchema(Schema):
    access_token = fields.Str(description="JWT access token")
    refresh_token = fields.Str(description="JWT refresh token")

class TimelineSchema(Schema):
    id = fields.Int(description="Timeline ID")
    name = fields.Str(description="Timeline name")
    description = fields.Str(description="Timeline description")
    created_at = fields.DateTime(description="Creation timestamp")

class ErrorSchema(Schema):
    error = fields.Str(description="Error message")
    status = fields.Int(description="HTTP status code")

# Create some simple API routes with documentation
@app.route('/api/health', methods=['GET'])
@doc(description='Check if the API is running', tags=['Utilities'])
@marshal_with(Schema.from_dict(
    {'status': fields.Str(), 'version': fields.Str()}
), code=200)
def health_check():
    """Check if the API is healthy"""
    return jsonify({
        'status': 'ok',
        'version': '1.0.0'
    })

@app.route('/api/login', methods=['POST'])
@doc(description='Log in and get your access tokens', tags=['Authentication'])
@use_kwargs(LoginSchema)
@marshal_with(TokenSchema, code=200)
@marshal_with(ErrorSchema, code=401)
def login(**kwargs):
    """User login endpoint"""
    # This is just a demo - we're not actually checking credentials
    return jsonify({
        'access_token': 'demo_access_token',
        'refresh_token': 'demo_refresh_token'
    })

@app.route('/api/timelines', methods=['GET'])
@doc(description='Get all your timelines', tags=['Timelines'])
@marshal_with(TimelineSchema(many=True), code=200)
def get_timelines():
    """Get all timelines for the current user"""
    # Return some demo data
    return jsonify([
        {
            'id': 1,
            'name': 'My First Timeline',
            'description': 'A timeline about my life',
            'created_at': datetime.datetime.now().isoformat()
        },
        {
            'id': 2,
            'name': 'Work History',
            'description': 'My career journey',
            'created_at': datetime.datetime.now().isoformat()
        }
    ])

# Register all the documented endpoints with the API docs
docs.register(health_check)
docs.register(login)
docs.register(get_timelines)

if __name__ == '__main__':
    print("Starting simple API docs demo...")
    print("Check out the docs at: http://localhost:5000/swagger-ui")
    app.run(debug=True)
