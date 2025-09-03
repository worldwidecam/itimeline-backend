# iTimeline Backend
(2025-08-22 – PostgreSQL migration complete; PostgreSQL is the default for local development and production.)
Backend server for the iTimeline application, a modern web application for creating and sharing timelines with interactive event cards.

## Important Configuration Notes

### CORS Configuration

**DO NOT** mix multiple CORS implementations as it will cause duplicate headers and break the application. The project uses `flask-cors` with the following configuration in `app.py`:

```python
# Enable CORS with specific settings
cors = CORS(
    app,
    resources={
        r"/*": {
            "origins": allowed_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization", "Accept", "X-Requested-With"],
            "expose_headers": ["Content-Type", "Authorization", "X-Total-Count"],
            "supports_credentials": True,
            "max_age": 600  # Cache preflight request for 10 minutes
        }
    }
)
```

**Important**: Do not add additional `@app.after_request` or `@app.before_request` handlers for CORS as they will conflict with the above configuration.

### Local vs Production Database Configuration

- For local development, `app.py` currently hardcodes the PostgreSQL URL in `app.config.update()['SQLALCHEMY_DATABASE_URI']` to ensure the app never tries to hit a remote Render DB during dev.
- Connection used locally: `postgresql://postgres:death2therich@localhost:5432/itimeline_test`.
- TODO (Production): Before deploying, switch back to environment-based configuration and remove the hardcoded URI. Example:
  - `SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'postgresql://postgres:death2therich@localhost:5432/itimeline_test')`
- If you need to test a different DB temporarily, you can still override at runtime:
  - PowerShell: `$env:DATABASE_URL = "postgresql://user:pass@host:5432/db"`
  - Bash: `export DATABASE_URL=postgresql://user:pass@host:5432/db`

### Development Best Practices

1. **Database Migrations**:
   - Always use SQLAlchemy migrations for schema changes
   - Never modify the database schema directly in production

2. **Environment Variables**:
   - Keep all sensitive configuration in environment variables
   - Use `.env` file for local development (add to `.gitignore`)
   - Document all required environment variables in this README

3. **Error Handling**:
   - Ensure all API endpoints have proper error handling
   - Log errors with appropriate context for debugging
   - Return consistent error response formats

4. **API Versioning**:
   - All API routes should be prefixed with `/api/v1/`
   - Document breaking changes when incrementing the API version

## Features

- RESTful API for timeline and event management
- User authentication with JWT
- File uploads with Cloudinary integration
- Database management with SQLAlchemy
- CORS support for cross-domain requests
- User-specific membership persistence with Passport system

### Community Admin Access UX (Frontend)
- The frontend now includes a `CommunityLockView` and an AdminPanel access-loading guard to prevent unauthorized content flashes during access checks.
- No backend route or schema changes were required for this UX improvement; existing membership and role checks remain the source of truth.

### User Passport System
- **Membership Levels**:
  1. **SiteOwner (User ID 1)**: Always has access to all timelines regardless of database state
     - Membership status is forced to true
     - Never sees "Join Community" buttons
     - Status persists across sessions and devices
  2. **Timeline Creators**: Automatically granted admin access to their own timelines
     - Membership is created during timeline creation
     - Fallback mechanism ensures admin access if record is missing
     - Status persists across sessions
  3. **Regular Members**: Must join timelines through the UI
     - Public timelines: Immediate membership
     - Private timelines: Requires approval from admins
     - Status is cached in localStorage with 30-minute expiration
- **Cross-Device Membership Persistence**: Maintains consistent timeline membership status across multiple devices and sessions
- **Server-Side Storage**: Stores user membership data in a dedicated `user_passport` table in the PostgreSQL database (via SQLAlchemy models)
- **User-Specific Caching**: Frontend caches passport data with consistent localStorage key format: `timeline_membership_${timelineId}`
- **Automatic Synchronization**: Passport syncs with backend after membership changes
- **Special Role Recognition**: Automatically recognizes timeline creators and site owners as members
- **API Endpoints**:
  - `GET /api/v1/user/passport`: Fetches the user's complete membership passport
  - `POST /api/v1/user/passport/sync`: Synchronizes the passport with the latest membership data
  - `GET /api/v1/timelines/{timelineId}/membership-status`: Checks membership status for a specific timeline
  - `POST /api/v1/timelines/{timelineId}/access-requests`: Sends a request to join a timeline

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
- **Database**: SQLAlchemy with PostgreSQL (default for local development and production)
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

5. Configure database connection (PostgreSQL):
   - Set `DATABASE_URL` for local dev (defaults to local Postgres if unset):
     ```bash
     # Example local connection string
     set DATABASE_URL=postgresql://postgres:death2therich@localhost:5432/itimeline_test  # Windows (PowerShell use $env:DATABASE_URL)
     export DATABASE_URL=postgresql://postgres:death2therich@localhost:5432/itimeline_test # macOS/Linux
     ```
   - Tables are created automatically on app start via SQLAlchemy. No SQLite file is used.

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

> **⚠️ IMPORTANT CAUTION**: While the application is configured for future deployment on Render.com, this is NOT the current focus. All development should prioritize local PostgreSQL functionality. Do not make changes specifically for Render.com deployment without explicit approval, as we are not yet ready for this step. Treat any Render.com specific configurations as cautionary and future-oriented.

The application is configured for future deployment on Render.com with the following setup:

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

The lists below reflect what is currently active in this codebase and what is the documented standard moving forward.

### Active (confirmed in code)
- **Passport**
  - `GET /api/v1/user/passport` — Fetch user's membership passport (see `app.py`)
  - `POST /api/v1/user/passport/sync` — Sync passport data (see `app.py`)

- **Uploads (Legacy path prefix)**
  - `POST /api/upload` — Generic upload (see `routes/upload.py` via `upload_bp`)
  - `POST /api/upload-media` — Media upload (see `routes/upload.py`)

- **Media Listing (Legacy path prefix)**
  - `GET /api/media-files` — Media listing (see `routes/media.py`)
  - `GET /api/cloudinary/audio-files` — Cloudinary audio listing (see `routes/cloudinary.py`)

### Documented Standard (`/api/v1`)
- All new endpoints should use `/api/v1/...`.
- Community and membership features are standardized under `/api/v1/membership/...`.
- Frontend docs list the canonical membership endpoints for client usage.

> Note: Some legacy endpoints still use `/api` (without version). They remain operational during the transition but are not recommended for new integrations.

### Serving Uploaded Files
- `GET /uploads/{filename}` — Serve uploaded files
- `GET /static/uploads/{filename}` — Serve uploaded files from static path

## Troubleshooting

- **Database Issues**: Ensure the app is using PostgreSQL.
  - Verify `DATABASE_URL` is set to your local PostgreSQL (e.g., `postgresql://postgres:death2therich@localhost:5432/itimeline_test`).
  - If needed, use the migration utilities in the `iTimeline-DB` package (e.g., migrate/reset/fix sequences).
- **File Upload Issues**: Check Cloudinary credentials and connectivity
- **CORS Issues**: Ensure the frontend URL is correctly set in the CORS configuration
- **Membership Persistence Issues**: Run `python fix_passport_sync.py` to synchronize all user passports with their actual membership data

### Migration Troubleshooting & Lessons Learned (PostgreSQL)

When a migration appears to “hang,” it’s almost always a Postgres table lock. Use this quick playbook.

1. **Run a read-only audit** (fast, safe)
   ```powershell
   python scripts/audit_schema.py
   ```
   - Confirms whether expected columns exist (e.g., `timeline_member.is_blocked`).

2. **If columns are missing, diagnose locks**
   - If `psql` is available:
     ```powershell
     psql "postgresql://postgres:death2therich@localhost:5432/itimeline_test" -c "SELECT pid, usename, state, wait_event_type, wait_event, query_start, left(query,200) AS query FROM pg_stat_activity WHERE datname = 'itimeline_test' ORDER BY query_start;"
     psql "postgresql://postgres:death2therich@localhost:5432/itimeline_test" -c "LOCK TABLE public.timeline_member IN ACCESS EXCLUSIVE MODE NOWAIT;"  # should error if locked
     ```
   - If `psql` is NOT available, use the included Python helper:
     ```powershell
     python find_blockers.py
     ```
     - Shows active sessions and current locks on `timeline_member`.

3. **Kill the blocker (local dev only; safe)**
   - With `psql`: `SELECT pg_terminate_backend(<PID>);`
   - Or use the included helper (edit PID if needed):
     ```powershell
     python kill_blocker.py
     ```

4. **Apply migration again**
   - The migration script `migrations/add_blocking_fields.py` now sets Postgres timeouts to fail fast and prints diagnostics on lock contention.
   ```powershell
   $env:DATABASE_URL='postgresql://postgres:death2therich@localhost:5432/itimeline_test'; python migrations/add_blocking_fields.py
   ```

5. **Verify**
   ```powershell
   python scripts/audit_schema.py
   ```

#### Why it hung (root cause)
PostgreSQL DDL (e.g., `ALTER TABLE`) requires an exclusive lock. Another session holding a long-lived transaction on the same table will cause the DDL to wait indefinitely. We observed a 2.5-hour exclusive lock on `timeline_member` blocking the migration. After terminating that backend PID and re-running, the migration completed immediately.

#### New helpers and defensive changes
- `migrations/add_blocking_fields.py` now sets:
  - `lock_timeout = '5s'`
  - `statement_timeout = '15s'`
  - On failure, it prints diagnostic info about potential blockers.
- Helper scripts (for local dev):
  - `find_blockers.py` — list sessions/locks and queries.
  - `kill_blocker.py` — terminate a known blocking PID, then apply DDL.
  - `quick_add_columns.py` — minimal DDL applier with short timeouts.
- Engine access utility:
  - `utils/db_helper.py#get_db_engine()` — consistent engine retrieval across Flask-SQLAlchemy versions.

#### PowerShell execution policy (if you use a venv)
- View policy: `Get-ExecutionPolicy -List`
- Temporary bypass (current window):
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\.venv\Scripts\Activate.ps1
  ```
- Per-user (recommended):
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
- You can always run Python without activating the venv by calling `.\.venv\Scripts\python.exe` directly.

### Fixing Membership Persistence

If users experience issues with their membership status not persisting across sessions:

1. **Verify Database Connection**: Ensure the backend is connecting to PostgreSQL via `DATABASE_URL` (SQLite file paths are legacy and no longer used)
2. **Check Passport Blueprint Registration**: Verify that `passport_bp` is registered in `app.py` with the prefix `/api/v1`
3. **Verify CORS Configuration**: Ensure CORS is properly configured to allow requests from the frontend
4. **Sync User Passports**: Run `python fix_passport_sync.py` to update all user passports with their complete membership data
5. **Frontend Storage Keys**: Ensure the frontend uses consistent localStorage key format: `timeline_membership_${timelineId}`

## Known Issues

### Legacy SQLite Path (Deprecated)

**Context**: Earlier versions referenced a local SQLite file path (e.g., `instance/timeline_forum.db`). The application now uses PostgreSQL for all environments.

**Action**: If you encounter references to SQLite paths, treat them as legacy notes. Ensure `DATABASE_URL` is configured and PostgreSQL is running.

### API Deprecation Policy

- **Deprecated**: Old, still-working endpoints or flows that will be removed in a future release.
- **Current Deprecated Items**:
  - Endpoints without `/api/v1`, including `/api/upload`, `/api/upload-media`, `/api/media-files`, and `/api/cloudinary/audio-files`.
  - Any `'/timelines/...'` routes without a version prefix.
- **Guidance**: Do not add new dependencies to deprecated endpoints. Prefer `/api/v1/...` routes. Migration work will consolidate all public APIs under `/api/v1`.

### Membership Persistence

**Issue Description**: Previously, user membership status would not persist correctly across login/logout cycles due to:
1. Missing passport blueprint registration in `app.py`
2. Incomplete synchronization between the `timeline_member` table and `user_passport` table
3. Inconsistent localStorage key formats in the frontend

**Resolution**: We've implemented a comprehensive fix that ensures:
- The passport blueprint is properly registered
- All user passports are fully synchronized with their membership data
- Special handling for creators and site owners is working correctly
- Frontend uses consistent localStorage key formats

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
