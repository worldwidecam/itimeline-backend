import sqlite3
import json
from datetime import datetime

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# Connect to the database
conn = sqlite3.connect('timeline_forum.db')
conn.row_factory = sqlite3.Row

# Create a cursor
cursor = conn.cursor()

# Get schema for timeline_member table
print("=== TIMELINE_MEMBER TABLE SCHEMA ===")
cursor.execute("PRAGMA table_info(timeline_member)")
schema = cursor.fetchall()
for column in schema:
    print(f"{column['name']} ({column['type']})")

# Get all community timelines
print("\n=== COMMUNITY TIMELINES ===")
cursor.execute("""
    SELECT id, name, timeline_type, visibility, created_by 
    FROM timeline 
    WHERE timeline_type = 'community'
""")
timelines = cursor.fetchall()

for timeline in timelines:
    print(f"\nTimeline ID: {timeline['id']}")
    print(f"Name: {timeline['name']}")
    print(f"Type: {timeline['timeline_type']}")
    print(f"Visibility: {timeline['visibility']}")
    print(f"Created by user ID: {timeline['created_by']}")
    
    # Get members for this timeline
    print("\nMembers:")
    cursor.execute("""
        SELECT tm.*, u.username 
        FROM timeline_member tm
        JOIN user u ON tm.user_id = u.id
        WHERE tm.timeline_id = ?
    """, (timeline['id'],))
    
    members = cursor.fetchall()
    if members:
        for member in members:
            member_dict = {key: member[key] for key in member.keys()}
            print(json.dumps(member_dict, indent=2, default=json_serial))
    else:
        print("No members found for this timeline")

# Close the connection
conn.close()
