"""add job_search.profile_id and search_posting join table

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-14

Profile-scoped searches (issue #24, v3 plan §2 D1–D3). Fixes the cross-profile
job leak at the data layer:

- `job_search.profile_id`: FK → `profile.id` ON DELETE CASCADE, NOT NULL after
  backfill. This was previously only echoed inside the `query` JSONB, so nothing
  could enforce scoping at the DB level.
- `search_posting`: append-only posting↔search many-to-many (unique
  `(search_id, posting_id)`). Replaces `job_posting.job_search_id`, which upsert
  re-fetches overwrote every run (a mutable, shared "results of this run"
  pointer).

Backfill (bulk SQL):
1. `job_search.profile_id` from `query->>'profile_id'` where it parses to an
   existing profile.
2. Remaining orphan rows adopt the single most-recently-updated profile —
   safe for this single-user app; recorded here per owner sign-off ⚠
   (v3 plan §8 risk: backfill ambiguity).
3. `search_posting` seeded from `job_posting.job_search_id`.

DOWNGRADE IS DESTRUCTIVE: `job_posting.job_search_id` is repopulated from
`search_posting` (first `created_at` per posting) — "which searches found this
posting" history collapses back to one pointer — and `search_posting` rows are
lost. Dropping `job_search.profile_id` discards search ownership entirely.

Changing the embedding model is unrelated to this migration; the pinned 768-dim
vector column is untouched.
"""

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _backfill_profile_id_from_query() -> None:
    """Owner from the stored request echo; only rows whose echo exists."""
    op.execute(
        text(
            "UPDATE job_search SET profile_id = (query->>'profile_id')::uuid "
            "WHERE profile_id IS NULL AND query ? 'profile_id' "
            "AND EXISTS (SELECT 1 FROM profile WHERE id = (query->>'profile_id')::uuid)"
        )
    )


def _adopt_orphans() -> None:
    """Orphan rows adopt the single most-recently-updated profile (single-user app)."""
    op.execute(
        text(
            "UPDATE job_search SET profile_id = sub.id FROM "
            "(SELECT id FROM profile ORDER BY updated_at DESC LIMIT 1) AS sub "
            "WHERE profile_id IS NULL"
        )
    )
    orphans = (
        op.get_bind()
        .execute(text("SELECT count(*) FROM job_search WHERE profile_id IS NULL"))
        .scalar_one()
    )
    if orphans:
        raise RuntimeError(
            "job_search rows with no profile to adopt found during backfill; "
            "the app requires at least one profile before searching"
        )


def _backfill_search_posting() -> None:
    op.execute(
        text(
            "INSERT INTO search_posting (search_id, posting_id) "
            "SELECT job_search_id, id FROM job_posting "
            "WHERE job_search_id IS NOT NULL ON CONFLICT DO NOTHING"
        )
    )


def upgrade() -> None:
    op.add_column(
        "job_search",
        sa.Column("profile_id", sa.Uuid(), nullable=True),
    )
    _backfill_profile_id_from_query()
    _adopt_orphans()
    op.alter_column("job_search", "profile_id", nullable=False)
    op.create_index(op.f("ix_job_search_profile_id"), "job_search", ["profile_id"])
    op.create_foreign_key(
        "fk_job_search_profile_id_profile",
        "job_search",
        "profile",
        ["profile_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "search_posting",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("search_id", sa.Uuid(), nullable=False),
        sa.Column("posting_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["search_id"],
            ["job_search.id"],
            ondelete="CASCADE",
            name="fk_search_posting_search_id_job_search",
        ),
        sa.ForeignKeyConstraint(
            ["posting_id"],
            ["job_posting.id"],
            ondelete="CASCADE",
            name="fk_search_posting_posting_id_job_posting",
        ),
        sa.UniqueConstraint(
            "search_id",
            "posting_id",
            name="uq_search_posting_search_posting",
        ),
    )
    op.create_index(op.f("ix_search_posting_search_id"), "search_posting", ["search_id"])
    op.create_index(op.f("ix_search_posting_posting_id"), "search_posting", ["posting_id"])

    _backfill_search_posting()

    op.drop_index(op.f("ix_job_posting_job_search_id"), table_name="job_posting")
    op.drop_constraint(op.f("job_posting_job_search_id_fkey"), "job_posting", type_="foreignkey")
    op.drop_column("job_posting", "job_search_id")


def downgrade() -> None:
    # Destructive: association history is repopulated one-pointer-per-posting,
    # remaining rows deleted, and search ownership dropped. See docstring.
    op.add_column("job_posting", sa.Column("job_search_id", sa.Uuid(), nullable=True))
    op.execute(
        text(
            "UPDATE job_posting AS p SET job_search_id = sp.search_id FROM "
            "(SELECT DISTINCT ON (posting_id) posting_id, search_id "
            "FROM search_posting ORDER BY posting_id, created_at ASC) AS sp "
            "WHERE sp.posting_id = p.id"
        )
    )
    op.create_foreign_key(
        op.f("job_posting_job_search_id_fkey"),
        "job_posting",
        "job_search",
        ["job_search_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_job_posting_job_search_id"), "job_posting", ["job_search_id"])

    op.drop_index(op.f("ix_search_posting_posting_id"), table_name="search_posting")
    op.drop_index(op.f("ix_search_posting_search_id"), table_name="search_posting")
    op.drop_table("search_posting")

    op.drop_constraint("fk_job_search_profile_id_profile", "job_search", type_="foreignkey")
    op.drop_index(op.f("ix_job_search_profile_id"), table_name="job_search")
    op.drop_column("job_search", "profile_id")
