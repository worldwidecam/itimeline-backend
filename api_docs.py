"""
API Documentation for iTimeline Backend

This file helps add nice interactive API docs to our Flask app.
It uses Flask-APISpec to create OpenAPI/Swagger docs that show what each API endpoint does.
Think of it as an automatic user manual for your API!
"""

from flask import Flask
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask_apispec.extension import FlaskApiSpec
from flask_apispec import use_kwargs, marshal_with, doc
from marshmallow import Schema, fields
import os
import sys

# Here's where we define what our API requests and responses look like
class UserSchema(Schema):
    id = fields.Int(description="User ID")
    username = fields.Str(description="Username")
    email = fields.Str(description="Email address")
    bio = fields.Str(description="User biography", allow_none=True)
    avatar_url = fields.Str(description="URL to user avatar", allow_none=True)
    created_at = fields.DateTime(description="Account creation timestamp")

class LoginRequestSchema(Schema):
    email = fields.Str(required=True, description="Email address")
    password = fields.Str(required=True, description="Password")

class RegisterRequestSchema(Schema):
    username = fields.Str(required=True, description="Username")
    email = fields.Str(required=True, description="Email address")
    password = fields.Str(required=True, description="Password")

class TokenResponseSchema(Schema):
    access_token = fields.Str(description="JWT access token")
    refresh_token = fields.Str(description="JWT refresh token")
    user = fields.Nested(UserSchema, description="User information")

class TimelineSchema(Schema):
    id = fields.Int(description="Timeline ID")
    name = fields.Str(description="Timeline name")
    description = fields.Str(description="Timeline description", allow_none=True)
    created_by = fields.Int(description="User ID of creator")
    created_at = fields.DateTime(description="Creation timestamp")
    timeline_type = fields.Str(description="Timeline type (hashtag, community, personal)", default="hashtag")
    visibility = fields.Str(description="Timeline visibility (public, private)", default="public")
    formatted_name = fields.Method("get_formatted_name", description="Formatted name with prefix (# or i-)")
    member_count = fields.Int(description="Number of members", dump_only=True)
    
    def get_formatted_name(self, obj):
        """Return the formatted name based on timeline type"""
        if hasattr(obj, 'get_formatted_name'):
            return obj.get_formatted_name()
        if hasattr(obj, 'timeline_type') and obj.timeline_type == 'community':
            return f"i-{obj.name}"
        return f"#{obj.name}"

class TimelineCreateSchema(Schema):
    name = fields.Str(required=True, description="Timeline name")
    description = fields.Str(description="Timeline description", allow_none=True)
    timeline_type = fields.Str(description="Timeline type (hashtag, community)", default="hashtag")
    visibility = fields.Str(description="Timeline visibility (public, private)", default="public")

class TimelineMemberSchema(Schema):
    id = fields.Int(description="Member ID")
    timeline_id = fields.Int(description="Timeline ID")
    user_id = fields.Int(description="User ID")
    role = fields.Str(description="Member role (admin, moderator, member)")
    joined_at = fields.DateTime(description="Join timestamp")
    invited_by = fields.Int(description="User ID of inviter", allow_none=True)
    user = fields.Nested("UserSchema", exclude=("email",), dump_only=True)

class TimelineMemberCreateSchema(Schema):
    user_id = fields.Int(required=True, description="User ID to add as member")
    role = fields.Str(description="Member role (admin, moderator, member)", default="member")

class EventTimelineAssociationSchema(Schema):
    id = fields.Int(description="Association ID")
    event_id = fields.Int(description="Event ID")
    timeline_id = fields.Int(description="Timeline ID")
    shared_by = fields.Int(description="User ID who shared the event")
    shared_at = fields.DateTime(description="Timestamp when shared")
    source_timeline_id = fields.Int(description="Source timeline ID", allow_none=True)
    shared_by_user = fields.Nested("UserSchema", exclude=("email",), dump_only=True)
    timeline = fields.Nested("TimelineSchema", exclude=("description",), dump_only=True)
    source_timeline = fields.Nested("TimelineSchema", exclude=("description",), dump_only=True, allow_none=True)

class EventSchema(Schema):
    id = fields.Int(description="Event ID")
    title = fields.Str(description="Event title")
    description = fields.Str(description="Event description", allow_none=True)
    event_date = fields.DateTime(description="Event date and time")
    raw_event_date = fields.Str(description="Raw event date string", allow_none=True)
    type = fields.Str(description="Event type (remark, news, media)")
    url = fields.Str(description="URL associated with the event", allow_none=True)
    url_title = fields.Str(description="Title extracted from URL", allow_none=True)
    url_description = fields.Str(description="Description extracted from URL", allow_none=True)
    url_image = fields.Str(description="Image URL extracted from URL", allow_none=True)
    media_url = fields.Str(description="Media URL for media type events", allow_none=True)
    media_type = fields.Str(description="Media type (image, video, audio)", allow_none=True)
    timeline_id = fields.Int(description="Timeline ID")
    created_by = fields.Int(description="User ID of creator")
    created_at = fields.DateTime(description="Creation timestamp")
    tags = fields.List(fields.Str(), description="List of tags for the event", allow_none=True)

class EventCreateSchema(Schema):
    title = fields.Str(required=True, description="Event title")
    description = fields.Str(description="Event description", allow_none=True)
    event_date = fields.Str(required=True, description="Event date and time")
    type = fields.Str(description="Event type (remark, news, media)", default="remark")
    url = fields.Str(description="URL associated with the event", allow_none=True)
    tags = fields.List(fields.Str(), description="List of tags for the event", allow_none=True)

class ErrorSchema(Schema):
    error = fields.Str(description="Error message")
    status = fields.Int(description="HTTP status code")

class SuccessSchema(Schema):
    message = fields.Str(description="Success message")
    status = fields.Int(description="HTTP status code")

class HealthCheckSchema(Schema):
    status = fields.Str(description="API status")
    version = fields.Str(description="API version")
    environment = fields.Str(description="Environment (development, production)")
    database = fields.Str(description="Database connection status")
    uptime = fields.Float(description="Server uptime in seconds")
    timestamp = fields.DateTime(description="Current server timestamp")

def setup_docs(app):
    """
    Gets the API docs ready for our Flask app.
    
    Just pass in your Flask app, and this function will set up all the 
    documentation config you need.
    
    Args:
        app: Your Flask app
    """
    app.config.update({
        'APISPEC_SPEC': APISpec(
            title='iTimeline API',
            version='1.0.0',
            openapi_version='3.0.2',
            plugins=[MarshmallowPlugin()],
            info={
                'description': 'API for the iTimeline application',
                'contact': {'email': 'support@i-timeline.com'},
                'license': {'name': 'MIT'},
            },
        ),
        'APISPEC_SWAGGER_UI_URL': '/swagger-ui',
        'APISPEC_SWAGGER_URL': '/openapi',
    })
    
    docs = FlaskApiSpec(app)
    
    # Register view functions with APISpec
    # This will be done by decorating the existing routes
    
    return docs

def register_docs(app):
    """
    Connects your API routes with their documentation.
    
    Call this function after you've set up all your routes.
    It adds documentation to your existing endpoints without changing how they work.
    
    Args:
        app: Your Flask app
    """
    docs = setup_docs(app)
    
    # Now we can register the routes with documentation
    # This is where we would add @doc, @use_kwargs, and @marshal_with decorators
    # to the existing routes
    
    return docs

# Here's a quick example of how to document a route
"""
@app.route('/api/login', methods=['POST'])
@doc(description='Log in and get your access tokens', tags=['Authentication'])
@use_kwargs(LoginRequestSchema, location='json')
@marshal_with(TokenResponseSchema, code=200)  # What success looks like
@marshal_with(ErrorSchema, code=401)  # What errors look like
def login():
    # Your existing login code stays the same
    pass
"""

if __name__ == "__main__":
    # This is just for testing the documentation setup
    app = Flask(__name__)
    docs = setup_docs(app)
    app.run(debug=True)
