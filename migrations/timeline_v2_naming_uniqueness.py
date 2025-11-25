"""Timeline V2 naming & uniqueness: move from global unique name to type-aware constraints.

This migration assumes the existing `timeline` table has columns:
- id (PK)
- name (String)
- timeline_type (String)
- created_by (FK to user.id)

It removes the global unique constraint on `name` that was previously implied by
`unique=True` in the SQLAlchemy model, and replaces it with:

- A unique index on (UPPER(name), timeline_type) for hashtag/community timelines.
- A unique index on (UPPER(name), timeline_type, created_by) for personal timelines.

IMPORTANT: This file does not attempt to detect or rename any conflicting rows.
Run data audits and cleanups prior to applying this in environments with
non-trivial data.
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision = "timeline_v2_naming_uniqueness"
down_revision = None  # Set this to the latest existing revision ID before running autogenerate
branch_labels = None
depends_on = None


def upgrade():
    """Apply type-aware uniqueness for timelines.

    Steps:
    1. Drop the legacy global unique constraint/index on timeline.name if present.
    2. Add new unique indexes enforcing:
       - (UPPER(name), timeline_type) for non-personal timelines.
       - (UPPER(name), timeline_type, created_by) for personal timelines.

    NOTE: The exact constraint/index names may differ by database backend. This
    migration uses defensive `try/except` blocks when dropping the old unique
    constraint to avoid hard failures if the name does not exist.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1) Try to drop any existing unique index/constraint on timeline.name
    existing_indexes = inspector.get_indexes("timeline")
    for idx in existing_indexes:
        cols = idx.get("column_names") or []
        if len(cols) == 1 and cols[0] == "name" and idx.get("unique"):
            op.drop_index(idx["name"], table_name="timeline")

    # Some databases may also expose a named unique constraint
    try:
        op.drop_constraint("timeline_name_key", "timeline", type_="unique")
    except Exception:
        # Constraint may not exist or may have a different name; ignore safely.
        pass

    # 2) Add new type-aware unique indexes
    # Unique per (UPPER(name), timeline_type) for hashtag/community
    op.create_index(
        "uq_timeline_name_type_upper",
        "timeline",
        [sa.text("upper(name)"), "timeline_type"],
        unique=True,
        postgresql_where=sa.text("timeline_type IN ('hashtag', 'community')"),
    )

    # Unique per (UPPER(name), timeline_type, created_by) for personal timelines
    op.create_index(
        "uq_timeline_name_type_owner_upper",
        "timeline",
        [sa.text("upper(name)"), "timeline_type", "created_by"],
        unique=True,
        postgresql_where=sa.text("timeline_type = 'personal'"),
    )


def downgrade():
    """Revert to global unique timeline.name.

    This removes the type-aware unique indexes and restores a simple unique
    constraint on `timeline.name`.
    """
    # Drop new type-aware unique indexes
    try:
        op.drop_index("uq_timeline_name_type_owner_upper", table_name="timeline")
    except Exception:
        pass

    try:
        op.drop_index("uq_timeline_name_type_upper", table_name="timeline")
    except Exception:
        pass

    # Re-add a global unique index/constraint on name
    # (You may need to adjust this to match your original schema.)
    op.create_unique_constraint("timeline_name_key", "timeline", ["name"])
