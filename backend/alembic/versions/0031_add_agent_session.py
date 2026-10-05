"""add_agent_session

Revision ID: 0031
Revises: 0030

v6 #58: `agent_session` (an interview-prep conversation per profile, optionally pinned to a
match; `profile_id` CASCADE, `match_id` SET NULL, `candidate_id` RESTRICT; `summary` and
`summarized_through` hold the rolling memory) and `agent_message` (one row per turn with
citations, grounding report and usage as JSONB; FK CASCADE). No existing table is changed.

Downgrade drops the two tables and the `agent_role` enum; saved conversations are lost.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.migration_helpers import create_updated_at_trigger, drop_updated_at_trigger

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _uuid_pk() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _jsonb(name: str, default: str) -> sa.Column[postgresql.JSONB]:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text(default),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "agent_session",
        _uuid_pk(),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("style_notes", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summarized_through", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("agent_session_candidate_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("agent_session_profile_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["match.id"],
            name=op.f("agent_session_match_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("agent_session_pkey")),
    )
    op.create_index(op.f("ix_agent_session_candidate_id"), "agent_session", ["candidate_id"])
    op.create_index(op.f("ix_agent_session_profile_id"), "agent_session", ["profile_id"])
    op.create_index(op.f("ix_agent_session_match_id"), "agent_session", ["match_id"])

    op.create_table(
        "agent_message",
        _uuid_pk(),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Enum("user", "assistant", name="agent_role"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=30), nullable=True),
        _jsonb("citations", "'[]'::jsonb"),
        _jsonb("grounding", "'{}'::jsonb"),
        _jsonb("usage", "'{}'::jsonb"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["agent_session.id"],
            name=op.f("agent_message_session_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("agent_message_pkey")),
    )
    op.create_index(op.f("ix_agent_message_session_id"), "agent_message", ["session_id"])
    op.create_index(
        "ix_agent_message_session_created", "agent_message", ["session_id", "created_at"]
    )

    create_updated_at_trigger("agent_session")


def downgrade() -> None:
    drop_updated_at_trigger("agent_session")
    op.drop_table("agent_message")
    op.drop_table("agent_session")
    op.execute(sa.text("DROP TYPE IF EXISTS agent_role"))
