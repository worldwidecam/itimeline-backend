#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories if they don't exist
mkdir -p instance

# Run any database migrations if needed
python manage.py db upgrade

# Additional setup steps can be added here
