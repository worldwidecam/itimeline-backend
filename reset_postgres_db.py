#!/usr/bin/env python3
"""
Reset PostgreSQL Database Script
Drops and recreates the database to apply schema changes
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configuration
POSTGRES_HOST = "localhost"
POSTGRES_PORT = "5432"
POSTGRES_USER = "postgres"
POSTGRES_DB = "itimeline_test"

def reset_database():
    """Drop and recreate the PostgreSQL database"""
    password = "death2therich"
    
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
        
        print(f"[INFO] Connected to PostgreSQL server")
        
        # Drop database if exists
        cursor.execute(f"DROP DATABASE IF EXISTS {POSTGRES_DB}")
        print(f"[SUCCESS] Dropped database '{POSTGRES_DB}' if it existed")
        
        # Create database
        cursor.execute(f"CREATE DATABASE {POSTGRES_DB}")
        print(f"[SUCCESS] Created database '{POSTGRES_DB}'")
        
        cursor.close()
        conn.close()
        
        print(f"[SUCCESS] Database reset completed successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error resetting database: {str(e)}")
        return False

if __name__ == "__main__":
    print("PostgreSQL Database Reset")
    print("=" * 40)
    reset_database()
