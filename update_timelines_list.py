# Update the get_timelines_v3 function to include timeline_type in the response
with open('app.py', 'r') as file:
    lines = file.readlines()

# Find the get_timelines_v3 function and modify the response
in_function = False
for i in range(len(lines)):
    if '@app.route(\'/api/timeline-v3\', methods=[\'GET\'])' in lines[i]:
        in_function = True
    
    if in_function and "'created_at': timeline.created_at.isoformat()" in lines[i]:
        # Add timeline_type after created_at
        lines[i] = lines[i].rstrip() + ",\n"
        lines.insert(i+1, "            'timeline_type': timeline.timeline_type\n")
        break

# Write the modified content back to the file
with open('app.py', 'w') as file:
    file.writelines(lines)

print("Successfully added timeline_type to the get_timelines_v3 response")
