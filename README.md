# iTimeline Backend

Backend server for the iTimeline application, a modern web application for creating and sharing timelines with interactive event cards.

## Features

- RESTful API for timeline and event management
- User authentication with JWT
- File uploads with Cloudinary integration
- Database management with SQLAlchemy
- CORS support for cross-domain requests

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

The backend provides the following main API endpoints:

- **Authentication**:
  - `POST /auth/register`: Register a new user
  - `POST /auth/login`: Log in an existing user
  - `POST /auth/logout`: Log out the current user

- **Timelines**:
  - `GET /timelines`: Get all timelines
  - `POST /timelines`: Create a new timeline
  - `GET /timelines/<id>`: Get a specific timeline
  - `PUT /timelines/<id>`: Update a timeline
  - `DELETE /timelines/<id>`: Delete a timeline

- **Events**:
  - `GET /events`: Get all events
  - `POST /events`: Create a new event
  - `GET /events/<id>`: Get a specific event
  - `PUT /events/<id>`: Update an event
  - `DELETE /events/<id>`: Delete an event

- **File Uploads**:
  - `POST /upload`: Upload a file
  - `GET /uploads/<filename>`: Serve a file

## Troubleshooting

- **Database Issues**: If you encounter database errors, try running `python reset_db.py` to reset the database
- **File Upload Issues**: Check Cloudinary credentials and connectivity
- **CORS Issues**: Ensure the frontend URL is correctly set in the CORS configuration
