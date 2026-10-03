"""set null on canonical posting delete

Issue #43 schema audit: `job_posting.canonical_id` is a provenance pointer with
no explicit ON DELETE (implicit NO ACTION). Per the standard it becomes
SET NULL: a duplicate whose canonical row is deleted turns into its own
canonical. Postings are never deleted by the app today, so no data changes.

Downgrade restores the implicit NO ACTION behaviour.
"""

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

FK_NAME = "fk_job_posting_canonical_id"


def upgrade() -> None:
    op.drop_constraint(FK_NAME, "job_posting", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME, "job_posting", "job_posting", ["canonical_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "job_posting", type_="foreignkey")
    op.create_foreign_key(FK_NAME, "job_posting", "job_posting", ["canonical_id"], ["id"])
