"""
Quick script to add requires_approval column to PostgreSQL timeline table.
Run this once to fix the schema.

Usage:
    python add_requires_approval_column.py
"""

from app import app, db
from sqlalchemy import text

def add_requires_approval_column():
    """Add requires_approval column to timeline table"""
    
    with app.app_context():
        try:
            # Check if column already exists
            check_sql = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='timeline' 
                AND column_name='requires_approval'
            """)
            
            result = db.session.execute(check_sql).fetchone()
            
            if result:
                print("✅ Column 'requires_approval' already exists!")
                return
            
            # Add the column
            print("Adding 'requires_approval' column to timeline table...")
            
            alter_sql = text("""
                ALTER TABLE timeline 
                ADD COLUMN requires_approval BOOLEAN DEFAULT FALSE NOT NULL
            """)
            
            db.session.execute(alter_sql)
            db.session.commit()
            
            print("✅ Successfully added 'requires_approval' column!")
            print("   - Type: BOOLEAN")
            print("   - Default: FALSE")
            print("   - Nullable: NO")
            
            # Verify
            verify_sql = text("""
                SELECT column_name, data_type, column_default, is_nullable
                FROM information_schema.columns 
                WHERE table_name='timeline' 
                AND column_name='requires_approval'
            """)
            
            result = db.session.execute(verify_sql).fetchone()
            if result:
                print(f"\n✅ Verification successful:")
                print(f"   Column: {result[0]}")
                print(f"   Type: {result[1]}")
                print(f"   Default: {result[2]}")
                print(f"   Nullable: {result[3]}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {str(e)}")
            raise

if __name__ == "__main__":
    print("="*60)
    print("Adding 'requires_approval' column to PostgreSQL")
    print("="*60)
    add_requires_approval_column()
    print("\n✅ Done! Restart your backend server.")
