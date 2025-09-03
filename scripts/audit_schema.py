import os
from typing import Dict, List

# SAFE TO DELETE: This script is read-only and used for temporary schema auditing.
# It performs no writes and can be safely removed during routine cleanup.

# Read-only schema audit for PostgreSQL
# - Prints available tables and columns
# - Compares critical expected columns for selected tables
# - No schema changes are performed

EXPECTED_COLUMNS: Dict[str, List[str]] = {
    # Focused on features we recently touched
    'timeline_member': [
        'id', 'timeline_id', 'user_id', 'role', 'is_active_member', 'joined_at', 'invited_by',
        # Blocking feature (may be missing if migration not applied)
        'is_blocked', 'blocked_at', 'blocked_reason',
    ],
    # Light checks for other key tables; this is not authoritative
    'user': ['id', 'username', 'email', 'avatar_url'],
    'timeline': ['id', 'created_by', 'timeline_type', 'created_at'],
}


def get_engine():
    """Create a direct SQLAlchemy engine from DATABASE_URL for read-only auditing.
    Avoids importing the Flask app entirely.
    """
    os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:death2therich@localhost:5432/itimeline_test')
    from sqlalchemy import create_engine
    return create_engine(os.environ['DATABASE_URL'])


def list_tables_and_columns(engine):
    from sqlalchemy import text

    with engine.begin() as conn:
        rows = conn.execute(text(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """
        )).mappings().all()

    tables: Dict[str, List[str]] = {}
    for r in rows:
        tables.setdefault(r['table_name'], []).append(r['column_name'])
    return tables


def print_report(tables: Dict[str, List[str]]):
    print("\n=== PostgreSQL Schema Audit (Read-Only) ===")
    print(f"Found {len(tables)} tables in schema 'public'.")

    # Summary list
    print("\nTables detected:")
    for t in sorted(tables.keys()):
        print(f"- {t} ({len(tables[t])} columns)")

    # Detailed column listing
    print("\nColumns by table:")
    for t in sorted(tables.keys()):
        cols = ', '.join(tables[t])
        print(f"  {t}: {cols}")

    # Expectations check for selected tables
    print("\nExpected critical columns (selected tables):")
    for table, expected_cols in EXPECTED_COLUMNS.items():
        actual = set(tables.get(table, []))
        missing = [c for c in expected_cols if c not in actual]
        status = "OK" if not missing else f"MISSING: {', '.join(missing)}"
        print(f"- {table}: {status}")


def main():
    try:
        engine = get_engine()
        tables = list_tables_and_columns(engine)
        print_report(tables)
    except Exception as e:
        print(f"Audit failed: {e}")


if __name__ == '__main__':
    main()
