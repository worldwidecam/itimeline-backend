"""
Setup script for Alembic database migrations.
Run this once to initialize Alembic for the project.

Usage:
    python setup_alembic.py
"""

import os
import subprocess
import sys

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"{'='*60}")
    print(f"Running: {command}")
    
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ Success!")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ Error!")
        if result.stderr:
            print(result.stderr)
        sys.exit(1)

def main():
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║         Alembic Database Migration Setup                  ║
    ║                                                            ║
    ║  This will set up Alembic for production-ready database   ║
    ║  migrations, preventing data loss from schema changes.    ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Check if alembic is already installed
    try:
        import alembic
        print("✅ Alembic is already installed")
    except ImportError:
        print("📦 Installing Alembic...")
        run_command(
            "pip install alembic",
            "Installing Alembic package"
        )
    
    # Initialize Alembic (only if not already initialized)
    if not os.path.exists('alembic'):
        run_command(
            "alembic init alembic",
            "Initializing Alembic directory structure"
        )
    else:
        print("✅ Alembic directory already exists")
    
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                    Setup Complete!                         ║
    ╚════════════════════════════════════════════════════════════╝
    
    Next steps:
    1. Review alembic.ini configuration
    2. Update alembic/env.py with your models
    3. Create your first migration: alembic revision --autogenerate -m "Initial migration"
    4. Apply migration: alembic upgrade head
    
    See MIGRATION_GUIDE.md for detailed instructions.
    """)

if __name__ == "__main__":
    main()
