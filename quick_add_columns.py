#!/usr/bin/env python3
"""
Quick DDL script to add blocking fields to timeline_member table.
Bypasses the migration script that hangs on locks.
"""
import os
import sys
from sqlalchemy import create_engine, text

def main():
    # Use hardcoded connection string for local dev
    db_url = "postgresql://postgres:death2therich@localhost:5432/itimeline_test"
    
    print(f"Connecting to: {db_url}")
    engine = create_engine(db_url)
    
    try:
        with engine.begin() as conn:
            print("Connected. Setting timeouts...")
            conn.execute(text("SET lock_timeout = '2s'"))
            conn.execute(text("SET statement_timeout = '10s'"))
            
            print("Adding columns...")
            
            # Add is_blocked
            conn.execute(text("ALTER TABLE public.timeline_member ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"))
            print("✓ Added is_blocked")
            
            # Add blocked_at  
            conn.execute(text("ALTER TABLE public.timeline_member ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP NULL"))
            print("✓ Added blocked_at")
            
            # Add blocked_reason
            conn.execute(text("ALTER TABLE public.timeline_member ADD COLUMN IF NOT EXISTS blocked_reason TEXT NULL"))
            print("✓ Added blocked_reason")
            
        print("✅ All columns added successfully!")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        
        # Try to show what's blocking
        try:
            with engine.connect() as conn:
                print("\nChecking for blockers...")
                result = conn.execute(text("""
                    SELECT pid, usename, state, wait_event_type, wait_event, 
                           left(query, 100) as query_snippet
                    FROM pg_stat_activity 
                    WHERE datname = current_database() 
                    AND state != 'idle'
                    ORDER BY query_start
                """)).fetchall()
                
                for row in result:
                    print(f"  PID {row[0]}: {row[1]} ({row[2]}) - {row[3]}/{row[4]} - {row[5]}")
                    
                if result:
                    print(f"\nTo kill a blocker: python -c \"from sqlalchemy import create_engine, text; engine = create_engine('{db_url}'); engine.execute(text('SELECT pg_terminate_backend(<PID>)'))\"")
                    
        except Exception as diag_e:
            print(f"Could not diagnose: {diag_e}")
        
        sys.exit(1)

if __name__ == "__main__":
    main()
