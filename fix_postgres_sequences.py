#!/usr/bin/env python3
"""
Fix PostgreSQL Sequences Script
Updates all sequence values to match the highest ID in each table
"""

import psycopg2

# Configuration
POSTGRES_HOST = "localhost"
POSTGRES_PORT = "5432"
POSTGRES_USER = "postgres"
POSTGRES_DB = "itimeline_test"

def fix_sequences():
    """Fix all PostgreSQL sequences to match current max IDs"""
    password = "death2therich"
    
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
        
        print("[INFO] Connected to PostgreSQL database")
        
        # Tables that have auto-incrementing ID fields
        tables_with_sequences = [
            ('user', 'user_id_seq'),
            ('timeline', 'timeline_id_seq'),
            ('event', 'event_id_seq'),
            ('tag', 'tag_id_seq'),
            ('timeline_member', 'timeline_member_id_seq'),
            ('timeline_action', 'timeline_action_id_seq'),
            ('user_music', 'user_music_id_seq'),
            ('event_timeline_association', 'event_timeline_association_id_seq'),
            ('post', 'post_id_seq'),
            ('comment', 'comment_id_seq'),
            ('token_blocklist', 'token_blocklist_id_seq')
        ]
        
        for table, sequence in tables_with_sequences:
            try:
                # Get the current max ID from the table
                cursor.execute(f'SELECT COALESCE(MAX(id), 0) FROM "{table}"')
                max_id = cursor.fetchone()[0]
                
                if max_id > 0:
                    # Set the sequence to max_id + 1
                    cursor.execute(f"SELECT setval('{sequence}', {max_id + 1})")
                    print(f"[SUCCESS] Fixed {table} sequence: set to {max_id + 1}")
                else:
                    print(f"[INFO] {table} is empty, skipping sequence fix")
                    
            except Exception as e:
                print(f"[WARNING] Could not fix sequence for {table}: {str(e)}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n[SUCCESS] PostgreSQL sequences fixed successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error fixing sequences: {str(e)}")
        return False

if __name__ == "__main__":
    print("PostgreSQL Sequence Fix")
    print("=" * 40)
    fix_sequences()
