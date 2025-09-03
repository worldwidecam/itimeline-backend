#!/usr/bin/env python3
"""
Find what's blocking the timeline_member table.
"""
import os
import sys
from sqlalchemy import create_engine, text

def main():
    db_url = "postgresql://postgres:death2therich@localhost:5432/itimeline_test"
    
    print(f"Connecting to: {db_url}")
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            print("Connected. Checking for active sessions...")
            
            result = conn.execute(text("""
                SELECT pid, usename, state, wait_event_type, wait_event, 
                       query_start, now() - query_start as duration,
                       left(query, 200) as query_snippet
                FROM pg_stat_activity 
                WHERE datname = current_database() 
                ORDER BY query_start
            """)).fetchall()
            
            print(f"\nFound {len(result)} active sessions:")
            for row in result:
                print(f"PID {row[0]}: user={row[1]}, state={row[2]}, wait={row[3]}/{row[4]}")
                print(f"  Duration: {row[6]}, Started: {row[5]}")
                print(f"  Query: {row[7]}")
                print()
            
            # Try to see what's specifically locking timeline_member
            print("Checking locks on timeline_member...")
            locks = conn.execute(text("""
                SELECT l.pid, l.mode, l.granted, a.usename, a.query
                FROM pg_locks l
                JOIN pg_stat_activity a ON l.pid = a.pid
                JOIN pg_class c ON l.relation = c.oid
                WHERE c.relname = 'timeline_member'
            """)).fetchall()
            
            if locks:
                print(f"Found {len(locks)} locks on timeline_member:")
                for lock in locks:
                    print(f"  PID {lock[0]}: mode={lock[1]}, granted={lock[2]}, user={lock[3]}")
                    print(f"    Query: {lock[4]}")
            else:
                print("No explicit locks found on timeline_member")
                
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
