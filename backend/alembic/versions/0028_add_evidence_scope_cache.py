"""add_evidence_scope_cache

Revision ID: 0028
Revises: 0027

The repository list is read from the database instead of GitHub on every page load. Each
`evidence_scope` row now keeps what the last refresh learned about the repository (fork flag,
description, last push, whether you contributed, whether GitHub still listed it, whether it was
first seen in the latest refresh), and `evidence_source` keeps when the list was last refreshed and
the token's reported scopes. No data migration: existing rows keep the defaults until the first
refresh, which the Evidence page triggers on its own.

Downgrade drops the columns; the cached listing metadata is lost (scopes, their selection and
everything synced from them are untouched).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _flag(name: str, *, default: str) -> sa.Column[bool]:
    return sa.Column(name, sa.Boolean(), server_default=sa.text(default), nullable=False)


def upgrade() -> None:
    op.add_column("evidence_scope", _flag("is_fork", default="false"))
    op.add_column("evidence_scope", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "evidence_scope", sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("evidence_scope", _flag("contributed", default="false"))
    op.add_column("evidence_scope", _flag("visible", default="true"))
    op.add_column("evidence_scope", _flag("new_since_refresh", default="false"))
    op.add_column(
        "evidence_source",
        sa.Column("scopes_refreshed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "evidence_source",
        sa.Column("token_scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence_source", "token_scopes")
    op.drop_column("evidence_source", "scopes_refreshed_at")
    op.drop_column("evidence_scope", "new_since_refresh")
    op.drop_column("evidence_scope", "visible")
    op.drop_column("evidence_scope", "contributed")
    op.drop_column("evidence_scope", "pushed_at")
    op.drop_column("evidence_scope", "description")
    op.drop_column("evidence_scope", "is_fork")
