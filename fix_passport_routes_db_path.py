import os
import shutil

def fix_passport_routes_db_path():
    """
    Update the database path in routes/passport.py to point to the correct location.
    """
    try:
        passport_file = 'routes/passport.py'
        print(f"Backing up {passport_file}...")
        # Create a backup of the original file
        shutil.copy2(passport_file, f"{passport_file}.bak")
        print(f"Backup created as {passport_file}.bak")
        
        print(f"\nUpdating database path in {passport_file}...")
        # Read the file
        with open(passport_file, 'r') as file:
            lines = file.readlines()
        
        # Update the database path
        updated_lines = []
        for line in lines:
            if "conn = sqlite3.connect('timeline_forum.db')" in line:
                updated_lines.append("        conn = sqlite3.connect('instance/timeline_forum.db')\n")
            else:
                updated_lines.append(line)
        
        # Write the updated content back to the file
        with open(passport_file, 'w') as file:
            file.writelines(updated_lines)
        
        print(f"Successfully updated database path in {passport_file}")
        print("The passport routes will now use 'instance/timeline_forum.db' instead of 'timeline_forum.db'")
        
        print("\nNext steps:")
        print("1. Restart the backend server")
        print("2. Test the join button functionality")
        print("3. Verify that membership status persists after logout and login")
        
    except Exception as e:
        print(f"Error updating {passport_file}: {str(e)}")

if __name__ == "__main__":
    fix_passport_routes_db_path()
