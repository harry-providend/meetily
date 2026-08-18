"""own summary templates per user

Templates move from "one row per id" to "one row per id per user", so the primary key gains the
owner columns. Autogenerate detects the new column but not the primary-key change, so that part
is written by hand.

Safe as an in-place alter because no environment has ever written a template row here: the
desktop app kept templates in its local SQLite until this change.

Revision ID: a3e3b83fb67c
Revises: 56c4ad36068a
Create Date: 2026-08-18 21:54:23.276355

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3e3b83fb67c"
down_revision: str | None = "56c4ad36068a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRIMARY_KEY = "summary_templates_pkey"


def upgrade() -> None:
    op.add_column("summary_templates", sa.Column("owner_user_id", sa.String(), nullable=False))
    op.alter_column(
        "summary_templates", "owner_tenant_id", existing_type=sa.VARCHAR(), nullable=False
    )
    op.drop_constraint(PRIMARY_KEY, "summary_templates", type_="primary")
    op.create_primary_key(
        PRIMARY_KEY, "summary_templates", ["owner_tenant_id", "owner_user_id", "id"]
    )


def downgrade() -> None:
    op.drop_constraint(PRIMARY_KEY, "summary_templates", type_="primary")
    op.create_primary_key(PRIMARY_KEY, "summary_templates", ["id"])
    op.alter_column(
        "summary_templates", "owner_tenant_id", existing_type=sa.VARCHAR(), nullable=True
    )
    op.drop_column("summary_templates", "owner_user_id")
