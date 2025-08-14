#!/usr/bin/env python3
"""
Complete PostgreSQL Migration Script for iTimeline Backend
Migrates from SQLite to PostgreSQL with full data preservation
"""

import os
import sys
import json
import sqlite3
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime
import getpass

# Configuration
SQLITE_DB_PATH = "instance/timeline_forum.db"
POSTGRES_HOST = "localhost"
POSTGRES_PORT = "5432"
POSTGRES_USER = "postgres"
POSTGRES_DB = "itimeline_test"
BACKUP_DIR = "migration_backup"

def print_step(step_num, title):
    """Print formatted step header"""
    print(f"\n[Step {step_num}]: {title}")
    print("=" * 60)

def create_backup_directory():
    """Create backup directory if it doesn't exist"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"[SUCCESS] Created backup directory: {BACKUP_DIR}")

def backup_sqlite_data():
    """Export all SQLite data to JSON files"""
    print_step(1, "Backing up SQLite data")
    
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"[ERROR] SQLite database not found at: {SQLITE_DB_PATH}")
        return False
    
    create_backup_directory()
    
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"[INFO] Found {len(tables)} tables to backup:")
        for table in tables:
            print(f"   - {table}")
        
        total_records = 0
        
        # Backup each table
        for table in tables:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries
            data = []
            for row in rows:
                row_dict = {}
                for key in row.keys():
                    value = row[key]
                    # Convert datetime strings to ISO format if needed
                    if isinstance(value, str) and ('created_at' in key or 'updated_at' in key or 'joined_at' in key or 'event_date' in key):
                        try:
                            # Try to parse and reformat datetime
                            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            row_dict[key] = dt.isoformat()
                        except:
                            row_dict[key] = value
                    else:
                        row_dict[key] = value
                data.append(row_dict)
            
            # Save to JSON file
            backup_file = os.path.join(BACKUP_DIR, f"{table}.json")
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            
            print(f"   [SUCCESS] {table}: {len(data)} records")
            total_records += len(data)
        
        conn.close()
        
        print(f"\n[SUCCESS] Backup completed successfully!")
        print(f"[INFO] Total records backed up: {total_records}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error backing up SQLite data: {str(e)}")
        return False

def test_postgres_connection(password):
    """Test PostgreSQL connection and create database if needed"""
    print_step(2, "Testing PostgreSQL connection")
    
    try:
        # Connect to PostgreSQL server (not specific database)
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=password
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("[SUCCESS] Connected to PostgreSQL server successfully!")
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DB,))
        if cursor.fetchone():
            print(f"[SUCCESS] Database '{POSTGRES_DB}' already exists")
        else:
            # Create database
            cursor.execute(f"CREATE DATABASE {POSTGRES_DB}")
            print(f"[SUCCESS] Database '{POSTGRES_DB}' created successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Error connecting to PostgreSQL: {str(e)}")
        return False

def create_postgres_tables(password):
    """Create PostgreSQL tables using SQLAlchemy models"""
    print_step(3, "Creating PostgreSQL tables")
    
    try:
        # Import Flask app to create tables
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Set environment variable for database URL
        os.environ['DATABASE_URL'] = f'postgresql://{POSTGRES_USER}:{password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'
        
        from app import app, db
        
        with app.app_context():
            # Create all tables
            db.create_all()
            print("[SUCCESS] All PostgreSQL tables created successfully!")
            return True
            
    except Exception as e:
        print(f"[ERROR] Error creating PostgreSQL tables: {str(e)}")
        return False

def import_postgres_data(password):
    """Import backed up data into PostgreSQL"""
    print_step(4, "Importing data into PostgreSQL")
    
    try:
        # Connect to PostgreSQL database
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=password,
            database=POSTGRES_DB
        )
        cursor = conn.cursor()
        
        # Import order to handle foreign key dependencies
        import_order = [
            'user',
            'user_music',
            'timeline',
            'timeline_member',
            'timeline_action',
            'tag',
            'event',
            'event_tags',
            'event_timeline_refs',
            'event_timeline_association',
            'post',
            'comment',
            'token_blocklist'
        ]
        
        total_imported = 0
        
        for table in import_order:
            backup_file = os.path.join(BACKUP_DIR, f"{table}.json")
            
            if not os.path.exists(backup_file):
                print(f"   [WARNING] Skipping {table} (no backup file)")
                continue
            
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                print(f"   [WARNING] Skipping {table} (no data)")
                continue
            
            # Get column names from first record
            columns = list(data[0].keys())
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join(columns)
            
            # Prepare INSERT statement with quoted table name to handle reserved keywords
            insert_sql = f'INSERT INTO "{table}" ({column_names}) VALUES ({placeholders})'
            
            # Insert data
            for record in data:
                values = []
                for col in columns:
                    value = record[col]
                    # Handle datetime conversion
                    if isinstance(value, str) and ('created_at' in col or 'updated_at' in col or 'joined_at' in col or 'event_date' in col):
                        try:
                            # Convert to proper datetime format
                            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            values.append(dt)
                        except:
                            values.append(value)
                    # Handle boolean conversion (SQLite stores as 0/1, PostgreSQL needs true/false)
                    elif isinstance(value, int) and ('is_' in col or col.endswith('_member') or col in ['promoted_to_event']):
                        values.append(bool(value))
                    else:
                        values.append(value)
                
                cursor.execute(insert_sql, values)
            
            conn.commit()
            print(f"   [SUCCESS] {table}: {len(data)} records imported")
            total_imported += len(data)
        
        cursor.close()
        conn.close()
        
        print(f"\n[SUCCESS] Data import completed successfully!")
        print(f"[INFO] Total records imported: {total_imported}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error importing data: {str(e)}")
        return False

def verify_migration(password):
    """Verify the migration was successful"""
    print_step(5, "Verifying migration")
    
    try:
        # Connect to PostgreSQL database
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=password,
            database=POSTGRES_DB
        )
        cursor = conn.cursor()
        
        # Check table counts
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        print(f"[INFO] Found {len(tables)} tables in PostgreSQL:")
        
        total_records = 0
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            count = cursor.fetchone()[0]
            print(f"   - {table}: {count} records")
            total_records += count
        
        cursor.close()
        conn.close()
        
        print(f"\n[SUCCESS] Migration verification completed!")
        print(f"[INFO] Total records in PostgreSQL: {total_records}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error verifying migration: {str(e)}")
        return False

def main():
    """Main migration function"""
    print("Complete PostgreSQL Migration")
    print("=" * 60)
    print("PostgreSQL Setup")
    
    # Get PostgreSQL password
    password = "death2therich"  # Using the provided password
    print("Using provided PostgreSQL password...")
    
    # Execute migration steps
    steps = [
        ("Backup SQLite data", backup_sqlite_data),
        ("Test PostgreSQL connection", lambda: test_postgres_connection(password)),
        ("Create PostgreSQL tables", lambda: create_postgres_tables(password)),
        ("Import data to PostgreSQL", lambda: import_postgres_data(password)),
        ("Verify migration", lambda: verify_migration(password))
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n[ERROR] Migration failed at: {step_name}")
            print("Please check the error messages above and try again.")
            return False
    
    print("\n[SUCCESS] PostgreSQL Migration Completed Successfully!")
    print("[SUCCESS] Your iTimeline backend is now running on PostgreSQL!")
    print("\nNext steps:")
    print("1. Restart your Flask application")
    print("2. Test all functionality")
    print("3. Update production environment variables")
    print("4. Deploy to Render.com with PostgreSQL")
    
    return True

if __name__ == "__main__":
    main()
