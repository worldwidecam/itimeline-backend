#!/usr/bin/env python3
"""
Kill the blocking transaction and apply the DDL.
"""
from sqlalchemy import create_engine, text

def main():
    db_url = "postgresql://postgres:death2therich@localhost:5432/itimeline_test"
    engine = create_engine(db_url)
    
    print("Killing blocker PID 13248...")
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_terminate_backend(13248)"))
        print("Killed PID 13248")
        
        # Wait a moment then apply DDL
        print("Applying DDL...")
        conn.execute(text("ALTER TABLE public.timeline_member ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"))
        print("Added is_blocked")
        
        conn.execute(text("ALTER TABLE public.timeline_member ADD COLUMN IF NOT EXISTS blocked_at TIMESTAMP NULL"))
        print("Added blocked_at")
        
        conn.execute(text("ALTER TABLE public.timeline_member ADD COLUMN IF NOT EXISTS blocked_reason TEXT NULL"))
        print("Added blocked_reason")
        
        conn.commit()
        print("Done!")

if __name__ == "__main__":
    main()
