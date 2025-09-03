from app import app, db
from sqlalchemy import text
import os

# Set DATABASE_URL to use PostgreSQL
os.environ['DATABASE_URL'] = 'postgresql://postgres:death2therich@localhost:5432/itimeline_test'

with app.app_context():
    with db.engine.begin() as conn:
        # First check if columns exist
        try:
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'timeline_member' AND column_name IN ('is_blocked', 'blocked_at', 'blocked_reason')")).fetchall()
            print(f"Blocking columns found: {[r[0] for r in result]}")
            
            if len(result) < 3:
                print("Missing blocking columns - need to run migration")
            else:
                members = conn.execute(text('SELECT user_id, is_active_member, is_blocked, blocked_reason FROM timeline_member WHERE timeline_id = 5')).mappings().all()
                print("Timeline 5 member status:")
                for m in members:
                    print(f'User {m["user_id"]}: active={m["is_active_member"]}, blocked={m["is_blocked"]}, reason={m["blocked_reason"]}')
        except Exception as e:
            print(f"Error: {e}")
