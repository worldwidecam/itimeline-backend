#!/usr/bin/env python
"""
Run the community info cards migration
"""
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from migrations.create_community_info_cards_table import create_community_info_cards_table, create_index
from app import app

if __name__ == '__main__':
    with app.app_context():
        print("Running migration: create_community_info_cards_table")
        if create_community_info_cards_table():
            if create_index():
                print("✅ Migration completed successfully")
            else:
                print("⚠️ Table created but index creation failed")
        else:
            print("❌ Migration failed")
