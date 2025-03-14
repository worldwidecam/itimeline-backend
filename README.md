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

## Key Dependencies

- `flask`: Web framework
- `flask-sqlalchemy`: Database ORM
- `flask-jwt-extended`: JWT authentication
- `flask-cors`: CORS handling
- `werkzeug`: File upload security
- `cloudinary`: Cloud storage for media files

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

## Setup and Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/itimeline-backend.git
   cd itimeline-backend
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up environment variables (optional for development):
   ```
   # For Cloudinary
   export CLOUDINARY_CLOUD_NAME=your_cloud_name
   export CLOUDINARY_API_KEY=your_api_key
   export CLOUDINARY_API_SECRET=your_api_secret
   
   # For JWT
   export JWT_SECRET_KEY=your_secret_key
   ```

5. Initialize the database:
   ```
   python init_db.py
   ```

6. Run the development server:
   ```
   python -m flask run
   ```

## API Endpoints

- `/api/auth/register` - Register a new user
- `/api/auth/login` - Login and get JWT token
- `/api/auth/refresh` - Refresh JWT token
- `/api/auth/logout` - Logout and invalidate token
- `/api/timeline` - Create and manage timelines
- `/api/events` - Create and manage events
- `/api/upload` - Upload files to Cloudinary
- `/api/profile` - User profile management

## Deployment

This application is designed to be deployed on Render as a Web Service.

## Environment Variables for Production

- `FLASK_ENV` - Set to 'production'
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET_KEY` - Secret key for JWT
- `CLOUDINARY_CLOUD_NAME` - Cloudinary cloud name
- `CLOUDINARY_API_KEY` - Cloudinary API key
- `CLOUDINARY_API_SECRET` - Cloudinary API secret
