"""One-off helper script to apply Timeline V2 naming & uniqueness rules directly.

This is a lightweight alternative to running the Alembic migration when the
Alembic environment is not fully initialized. It performs the same operations
as the `upgrade()` function in `migrations/timeline_v2_naming_uniqueness.py`:

- Drops the legacy global unique constraint on `timeline.name` (if it exists).
- Creates new type-aware unique indexes:
  - (UPPER(name), timeline_type) for hashtag & community timelines.
  - (UPPER(name), timeline_type, created_by) for personal timelines.

Run this ONCE against your Postgres dev database:

    python apply_timeline_v2_naming_uniqueness_direct.py

Make sure the backend server (python app.py) is NOT running while you run this.
"""

from sqlalchemy import text

from app import app, db


def apply_timeline_v2_naming_uniqueness():
    """Apply type-aware uniqueness for timelines using raw SQL.

    This is Postgres-specific and mirrors the intent of the Alembic migration:
    - Remove any global unique constraint on timeline.name.
    - Add partial unique indexes for hashtag/community and personal timelines.
    """
    with app.app_context():
        engine = db.engine
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                print("Applying Timeline V2 naming & uniqueness rules...")

                # 1) Drop new indexes if they already exist (idempotent re-run safety)
                conn.execute(
                    text(
                        """
                        DO $$
                        BEGIN
                            IF EXISTS (
                                SELECT 1 FROM pg_class c
                                JOIN pg_namespace n ON n.oid = c.relnamespace
                                WHERE c.relkind = 'i'
                                  AND c.relname = 'uq_timeline_name_type_owner_upper'
                            ) THEN
                                DROP INDEX uq_timeline_name_type_owner_upper;
                            END IF;

                            IF EXISTS (
                                SELECT 1 FROM pg_class c
                                JOIN pg_namespace n ON n.oid = c.relnamespace
                                WHERE c.relkind = 'i'
                                  AND c.relname = 'uq_timeline_name_type_upper'
                            ) THEN
                                DROP INDEX uq_timeline_name_type_upper;
                            END IF;
                        END
                        $$;
                        """
                    )
                )

                # 2) Drop legacy global unique constraint on timeline.name if present
                conn.execute(
                    text(
                        """
                        ALTER TABLE timeline
                        DROP CONSTRAINT IF EXISTS timeline_name_key;
                        """
                    )
                )

                # 3) Create new type-aware unique indexes
                conn.execute(
                    text(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS uq_timeline_name_type_upper
                        ON timeline (upper(name), timeline_type)
                        WHERE timeline_type IN ('hashtag', 'community');
                        """
                    )
                )

                conn.execute(
                    text(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS uq_timeline_name_type_owner_upper
                        ON timeline (upper(name), timeline_type, created_by)
                        WHERE timeline_type = 'personal';
                        """
                    )
                )

                trans.commit()
                print("✅ Timeline V2 naming & uniqueness applied successfully.")
            except Exception as e:
                trans.rollback()
                print("❌ Error applying Timeline V2 naming & uniqueness:", e)
                raise


if __name__ == "__main__":
    apply_timeline_v2_naming_uniqueness()
