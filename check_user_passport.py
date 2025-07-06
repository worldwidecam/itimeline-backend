#!/usr/bin/env python3
"""
Script to check the user_passport table and its contents.
This helps verify that the passport system is working correctly.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime

# Configuration
DB_PATH = "timeline_forum.db"  # Match the database path used in app.py

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {text} ==={Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}[SUCCESS] {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}[ERROR] {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}[INFO] {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}[WARNING] {text}{Colors.ENDC}")

def check_table_exists():
    """Check if the user_passport table exists in the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='user_passport'
    """)
    
    exists = cursor.fetchone() is not None
    conn.close()
    
    return exists

def get_all_passports():
    """Get all user passports from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM user_passport")
    
    rows = cursor.fetchall()
    passports = []
    
    for row in rows:
        try:
            memberships_json = json.loads(row["memberships_json"])
            passports.append({
                "user_id": row["user_id"],
                "memberships_count": len(memberships_json),
                "last_updated": row["last_updated"]
            })
        except json.JSONDecodeError:
            passports.append({
                "user_id": row["user_id"],
                "memberships_count": "ERROR: Invalid JSON",
                "last_updated": row["last_updated"]
            })
    
    conn.close()
    return passports

def get_user_details():
    """Get basic user details to correlate with passports"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, username, email FROM user")
    
    rows = cursor.fetchall()
    users = {}
    
    for row in rows:
        users[row["id"]] = {
            "username": row["username"],
            "email": row["email"]
        }
    
    conn.close()
    return users

def get_passport_details(user_id):
    """Get detailed information about a specific user's passport"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM user_passport WHERE user_id = ?",
        (user_id,)
    )
    
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
    
    try:
        memberships_json = json.loads(row["memberships_json"])
        
        # Get timeline details for each membership
        timeline_details = {}
        for membership in memberships_json:
            timeline_id = membership.get("timeline_id")
            if timeline_id:
                cursor.execute(
                    "SELECT name, visibility, timeline_type FROM timeline WHERE id = ?",
                    (timeline_id,)
                )
                timeline = cursor.fetchone()
                if timeline:
                    timeline_details[timeline_id] = {
                        "name": timeline["name"],
                        "visibility": timeline["visibility"],
                        "type": timeline["timeline_type"]
                    }
        
        passport = {
            "user_id": row["user_id"],
            "memberships": memberships_json,
            "timeline_details": timeline_details,
            "last_updated": row["last_updated"]
        }
    except json.JSONDecodeError:
        passport = {
            "user_id": row["user_id"],
            "memberships": "ERROR: Invalid JSON",
            "last_updated": row["last_updated"]
        }
    
    conn.close()
    return passport

def main():
    print_header("USER PASSPORT DATABASE CHECK")
    
    # Check if the table exists
    if not check_table_exists():
        print_error("The user_passport table does not exist in the database!")
        print_info("Run the create_user_passport_table.py script to create it.")
        return
    
    print_success("The user_passport table exists in the database.")
    
    # Get all passports
    passports = get_all_passports()
    users = get_user_details()
    
    print_info(f"Found {len(passports)} user passports in the database.")
    
    # Display summary of all passports
    print_header("PASSPORT SUMMARY")
    
    for passport in passports:
        user_id = passport["user_id"]
        user = users.get(user_id, {"username": "Unknown", "email": "Unknown"})
        
        print(f"User ID: {user_id} ({user['username']} / {user['email']})")
        print(f"  Memberships: {passport['memberships_count']}")
        print(f"  Last Updated: {passport['last_updated']}")
        print("")
    
    # Ask if user wants to see details for a specific user
    while True:
        user_input = input("\nEnter a user ID to see detailed passport info (or 'q' to quit): ")
        
        if user_input.lower() == 'q':
            break
        
        try:
            user_id = int(user_input)
            passport = get_passport_details(user_id)
            
            if not passport:
                print_warning(f"No passport found for user ID {user_id}")
                continue
            
            print_header(f"PASSPORT DETAILS FOR USER {user_id}")
            
            if isinstance(passport["memberships"], str) and passport["memberships"].startswith("ERROR"):
                print_error(passport["memberships"])
                continue
            
            print(f"Last Updated: {passport['last_updated']}")
            print(f"Memberships Count: {len(passport['memberships'])}")
            print("\nMemberships:")
            
            for i, membership in enumerate(passport["memberships"]):
                timeline_id = membership.get("timeline_id")
                timeline = passport["timeline_details"].get(timeline_id, {})
                
                print(f"\n{i+1}. Timeline ID: {timeline_id}")
                print(f"   Timeline Name: {timeline.get('name', 'Unknown')}")
                print(f"   Timeline Type: {timeline.get('type', 'Unknown')}")
                print(f"   Visibility: {timeline.get('visibility', 'Unknown')}")
                print(f"   Role: {membership.get('role', 'Unknown')}")
                print(f"   Is Creator: {membership.get('is_creator', False)}")
                print(f"   Is Site Owner: {membership.get('is_site_owner', False)}")
                print(f"   Joined At: {membership.get('joined_at', 'Unknown')}")
            
        except ValueError:
            print_error("Please enter a valid user ID (integer)")
        except Exception as e:
            print_error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
