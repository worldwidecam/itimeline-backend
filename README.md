# iTimeline Backend

Backend server for the iTimeline application, a modern web application for creating and sharing timelines with interactive event cards.

## Features

- RESTful API for timeline and event management
- User authentication with JWT
- File uploads with Cloudinary integration
- Database management with SQLAlchemy
- CORS support for cross-domain requests

### Date and Time Handling
- **Raw Event Date Storage**: Stores event dates in the `raw_event_date` column as strings in the format `MM.DD.YYYY.HH.MM.AMPM`
- **Exact User Time Flag**: Uses the `is_exact_user_time` boolean flag to prioritize user-selected times over server times
- **Timezone-Independent Processing**: Ensures accurate representation of event times regardless of server timezone
- **Dual Timestamp System**:
  - **Event Date**: The user-selected date and time for the event (stored in both ISO format and raw string format)
  - **Published Date**: The server timestamp when the event was created (automatically generated)
- **Backward Compatibility**: Maintains support for events created before the raw date string implementation

## Technical Stack

- **Framework**: Flask (Python)
- **Database**: SQLAlchemy with SQLite (PostgreSQL in production)
- **Authentication**: Flask-JWT-Extended
- **File Storage**: Cloudinary cloud storage
- **File Uploads**: Flask's built-in file handling
- **Deployment**: Docker containerization for Render.com

## Key Dependencies

- `flask`: Web framework
- `flask-sqlalchemy`: Database ORM
- `flask-jwt-extended`: JWT authentication
- `flask-cors`: CORS handling
- `werkzeug`: File upload security
- `cloudinary`: Cloud storage for media files
- `gunicorn`: WSGI HTTP Server for production deployment

## Cloud Storage Integration

- **Cloudinary Integration**: Implemented for persistent file storage
  - **Purpose**: Solves the ephemeral file system issue on Render hosting
  - **Features**:
    - Automatic image optimization (quality and format)
    - Image transformations (resizing, cropping, effects)
    - Audio file optimization
    - Thumbnail generation
  - **Configuration**:
    - Set environment variables in production:
      - `CLOUDINARY_CLOUD_NAME`
      - `CLOUDINARY_API_KEY`
      - `CLOUDINARY_API_SECRET`

## Repository Structure

This repository contains only the backend code for the iTimeline application. The frontend code is maintained in a separate repository at [itimeline-frontend](https://github.com/worldwidecam/itimeline-frontend).

## Setup and Installation

### Local Development

1. Clone the repository:
   ```
   git clone https://github.com/worldwidecam/itimeline-backend.git
   cd itimeline-backend
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```
   export FLASK_APP=app.py
   export FLASK_ENV=development
   export JWT_SECRET_KEY=your_secret_key
   ```
   For Cloudinary integration (optional for local development):
   ```
   export CLOUDINARY_CLOUD_NAME=your_cloud_name
   export CLOUDINARY_API_KEY=your_api_key
   export CLOUDINARY_API_SECRET=your_api_secret
   ```

5. Initialize the database:
   ```
   python init_db.py
   ```

6. Run the development server:
   ```
   flask run
   ```

### Using Docker for Local Development

1. Build and start the container:
   ```
   docker-compose up
   ```

## Deployment

The application is configured for deployment on Render.com with the following setup:

1. **Web Service**:
   - Build Command: `./build.sh`
   - Start Command: `gunicorn app:app`
   - Environment Variables:
     - `PYTHON_VERSION`: 3.12.0
     - `DATABASE_URL`: Automatically set by Render
     - `JWT_SECRET_KEY`: Generate a secure random string
     - `FRONTEND_URL`: Your frontend URL (e.g., https://i-timeline.com)
     - `CLOUDINARY_CLOUD_NAME`: Your Cloudinary cloud name
     - `CLOUDINARY_API_KEY`: Your Cloudinary API key
     - `CLOUDINARY_API_SECRET`: Your Cloudinary API secret

2. **Database**:
   - PostgreSQL database is automatically provisioned by Render

## API Documentation

We've added interactive API documentation to make development easier and more fun!

### Documentation Features

- **Interactive API Explorer**: Try out API calls right in your browser
- **Request/Response Examples**: See exactly what data to send and what you'll get back
- **Authentication Support**: Test protected endpoints with your JWT token
- **Organized by Category**: Endpoints grouped by function (auth, timelines, events, etc.)

### How to Use the Documentation

1. **Start the Documentation Server**:
   ```bash
   python docs_integration.py
   ```

2. **Access the Documentation**:
   - **OpenAPI JSON**: http://localhost:5000/openapi
   - **Interactive UI**: http://localhost:5000/swagger-ui

3. **Explore and Test**:
   - Browse the available endpoints
   - Click on any endpoint to see details
   - Try out API calls directly from the UI
   - See response codes and formats

### Documentation Files

- **api_docs.py**: Defines schemas and documentation setup
- **docs_integration.py**: Connects documentation to existing endpoints
- **simple_docs_demo.py**: Simplified example for quick testing

### Adding to Render Deployment

To enable API documentation on your Render deployment:

1. Add these dependencies to your `requirements.txt`:
   ```bash
   apispec>=1.0.0
   flask-apispec>=0.8.0
   ```

2. Push the documentation files to your repository

3. Update your Render service to run with documentation enabled

## API Endpoints

The backend provides the following API endpoints:

### Authentication
- **POST /auth/register**: Register a new user
- **POST /auth/login**: Log in an existing user
- **POST /auth/logout**: Log out the current user

### Timelines
- **GET /timelines**: Get all timelines
- **POST /timelines**: Create a new timeline
- **GET /timelines/<id>**: Get a specific timeline
- **PUT /timelines/<id>**: Update a timeline
- **DELETE /timelines/<id>**: Delete a timeline

### Events
- **GET /events**: Get all events
- **POST /events**: Create a new event
- **GET /events/<id>**: Get a specific event
- **PUT /events/<id>**: Update an event
- **DELETE /events/<id>**: Delete an event

### File Uploads
- **POST /upload**: Upload a file
- **GET /uploads/<filename>**: Serve a file

## Troubleshooting

- **Database Issues**: If you encounter database errors, try running `python reset_db.py` to reset the database
- **File Upload Issues**: Check Cloudinary credentials and connectivity
- **CORS Issues**: Ensure the frontend URL is correctly set in the CORS configuration

## Known Issues

### Media File Serving for Event Cards

**Issue Description**: Media files uploaded via the `/api/upload-media` endpoint are not displaying correctly in the frontend MediaCard and EventPopup components, despite being successfully uploaded to the server.

**Current Status**: As of March 25, 2025, we've attempted several approaches to fix this issue:

1. Added detailed logging to the upload_media function to confirm files are being saved correctly
2. Created a dedicated route (`/uploads/<filename>`) for serving uploaded files with explicit cache control headers
3. Updated the CORS configuration to allow all origins to access resources
4. Ensured the static file serving configuration is correctly set up
5. Verified that the upload directory exists and has proper permissions

**Troubleshooting Findings**:
- The upload_media endpoint successfully receives and saves files to the server
- The endpoint returns the correct URL path for the uploaded files
- The static file serving functionality appears to be working for other static assets
- Despite these changes, media files are not being displayed in the frontend

**Possible Causes**:
- There might be an issue with how the static files are being served from the uploads directory
- The URL format returned by the upload_media endpoint might not be compatible with how the frontend expects to receive it
- There could be permission issues with the uploaded files
- Browser caching might be preventing the media from displaying

**Next Steps**:
- Compare the implementation with the working profile avatar and music upload functionality
- Test the file serving routes directly in a browser to ensure they're accessible
- Consider implementing a different approach to file storage and retrieval
- Investigate potential MIME type issues with the served files

This issue is a high priority for the next development sprint.
