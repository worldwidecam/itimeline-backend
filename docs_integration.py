"""
iTimeline API Documentation Integration

This file shows you how to add documentation to your existing Flask routes.
It includes ready-to-use examples for your main API endpoints without changing your actual code.
Just run this file to see your API docs in action!
"""

from flask import Flask
from api_docs import (
    setup_docs, UserSchema, LoginRequestSchema, RegisterRequestSchema, 
    TokenResponseSchema, TimelineSchema, TimelineCreateSchema, 
    EventSchema, EventCreateSchema, ErrorSchema, SuccessSchema, HealthCheckSchema
)
from flask_apispec import use_kwargs, marshal_with, doc

# Import your existing app
from app import app

# Set up API documentation
docs = setup_docs(app)

# =============================================
# How to document your login/register endpoints
# =============================================

# Document the login endpoint
login_view = app.view_functions['login']
login_view = doc(
    description='Authenticate a user and get JWT tokens',
    tags=['Authentication']
)(login_view)
login_view = use_kwargs(
    LoginRequestSchema, 
    location='json'
)(login_view)
login_view = marshal_with(
    TokenResponseSchema, 
    code=200, 
    description='Successful login'
)(login_view)
login_view = marshal_with(
    ErrorSchema, 
    code=401, 
    description='Invalid credentials'
)(login_view)
app.view_functions['login'] = login_view
docs.register(login_view)

# Document the register endpoint
register_view = app.view_functions['register']
register_view = doc(
    description='Register a new user account',
    tags=['Authentication']
)(register_view)
register_view = use_kwargs(
    RegisterRequestSchema, 
    location='json'
)(register_view)
register_view = marshal_with(
    TokenResponseSchema, 
    code=201, 
    description='User successfully registered'
)(register_view)
register_view = marshal_with(
    ErrorSchema, 
    code=400, 
    description='Invalid registration data'
)(register_view)
app.view_functions['register'] = register_view
docs.register(register_view)

# =============================================
# How to document your timeline endpoints
# =============================================

# Document the create timeline endpoint
create_timeline_view = app.view_functions['create_timeline_v3']
create_timeline_view = doc(
    description='Create a new timeline',
    tags=['Timelines']
)(create_timeline_view)
create_timeline_view = use_kwargs(
    TimelineCreateSchema, 
    location='json'
)(create_timeline_view)
create_timeline_view = marshal_with(
    TimelineSchema, 
    code=201, 
    description='Timeline successfully created'
)(create_timeline_view)
create_timeline_view = marshal_with(
    ErrorSchema, 
    code=400, 
    description='Invalid timeline data'
)(create_timeline_view)
app.view_functions['create_timeline_v3'] = create_timeline_view
docs.register(create_timeline_view)

# Document the get timeline endpoint
get_timeline_view = app.view_functions['get_timeline_v3']
get_timeline_view = doc(
    description='Get a timeline by ID',
    tags=['Timelines']
)(get_timeline_view)
get_timeline_view = marshal_with(
    TimelineSchema, 
    code=200, 
    description='Timeline details'
)(get_timeline_view)
get_timeline_view = marshal_with(
    ErrorSchema, 
    code=404, 
    description='Timeline not found'
)(get_timeline_view)
app.view_functions['get_timeline_v3'] = get_timeline_view
docs.register(get_timeline_view)

# =============================================
# How to document your event endpoints
# =============================================

# Document the create event endpoint
create_event_view = app.view_functions['create_timeline_v3_event']
create_event_view = doc(
    description='Create a new event in a timeline',
    tags=['Events']
)(create_event_view)
create_event_view = use_kwargs(
    EventCreateSchema, 
    location='json'
)(create_event_view)
create_event_view = marshal_with(
    EventSchema, 
    code=201, 
    description='Event successfully created'
)(create_event_view)
create_event_view = marshal_with(
    ErrorSchema, 
    code=400, 
    description='Invalid event data'
)(create_event_view)
app.view_functions['create_timeline_v3_event'] = create_event_view
docs.register(create_event_view)

# Document the get timeline events endpoint
get_events_view = app.view_functions['get_timeline_v3_events']
get_events_view = doc(
    description='Get all events for a timeline',
    tags=['Events']
)(get_events_view)
get_events_view = marshal_with(
    EventSchema(many=True), 
    code=200, 
    description='List of timeline events'
)(get_events_view)
get_events_view = marshal_with(
    ErrorSchema, 
    code=404, 
    description='Timeline not found'
)(get_events_view)
app.view_functions['get_timeline_v3_events'] = get_events_view
docs.register(get_events_view)

# =============================================
# How to document your utility endpoints
# =============================================

# Document the health check endpoint
health_check_view = app.view_functions['health_check']
health_check_view = doc(
    description='Check the health status of the API',
    tags=['Utilities']
)(health_check_view)
health_check_view = marshal_with(
    HealthCheckSchema, 
    code=200, 
    description='API health information'
)(health_check_view)
app.view_functions['health_check'] = health_check_view
docs.register(health_check_view)

# Document the URL preview endpoint
url_preview_view = app.view_functions['url_preview']
url_preview_view = doc(
    description='Get preview information for a URL',
    tags=['Utilities']
)(url_preview_view)
url_preview_view = marshal_with(
    dict(
        title=fields.Str(),
        description=fields.Str(),
        image=fields.Str(),
        url=fields.Str(),
        domain=fields.Str()
    ), 
    code=200, 
    description='URL preview data'
)(url_preview_view)
url_preview_view = marshal_with(
    ErrorSchema, 
    code=400, 
    description='Invalid URL or unable to fetch preview'
)(url_preview_view)
app.view_functions['url_preview'] = url_preview_view
docs.register(url_preview_view)

# =============================================
# How to run your app with the new docs
# =============================================

if __name__ == '__main__':
    print("Starting iTimeline API with the fancy new docs...")
    print("API documentation (JSON format): http://localhost:5000/openapi")
    print("Interactive docs (much nicer to use): http://localhost:5000/swagger-ui")
    app.run(host='0.0.0.0', port=5000, debug=True)
