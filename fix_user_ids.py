#!/usr/bin/env python

"""
Script to fix hardcoded user IDs in the iTimeline backend application.
This script replaces hardcoded user IDs with the authenticated user's ID.
"""

import re

# Path to the app.py file
APP_FILE = 'app.py'

# Read the current content of the file
with open(APP_FILE, 'r', encoding='utf-8') as file:
    content = file.read()

# Replace the first instance of hardcoded user ID in the event creation function
pattern1 = r'(\s+created_by=)1,(\s+# Temporary default user ID)'
replacement1 = r'\1current_user_id,\2'
content = re.sub(pattern1, replacement1, content)

# Replace the second instance of hardcoded user ID in the event creation function
pattern2 = r'(\s+created_by=)1,(\s+# Temporary default user ID)'
replacement2 = r'\1current_user_id,\2'
content = re.sub(pattern2, replacement2, content)

# Write the updated content back to the file
with open(APP_FILE, 'w', encoding='utf-8') as file:
    file.write(content)

print("Successfully updated hardcoded user IDs in app.py")
