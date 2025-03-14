import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from datetime import datetime
from sqlalchemy import text

def upgrade():
    # Create token_blocklist table
    with db.engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS token_blocklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jti VARCHAR(36) NOT NULL UNIQUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user (id)
            );
        '''))
        conn.execute(text('CREATE INDEX IF NOT EXISTS ix_token_blocklist_jti ON token_blocklist (jti);'))
        conn.commit()

def downgrade():
    with db.engine.connect() as conn:
        conn.execute(text('DROP TABLE IF EXISTS token_blocklist;'))
        conn.commit()

if __name__ == '__main__':
    with app.app_context():
        upgrade()
