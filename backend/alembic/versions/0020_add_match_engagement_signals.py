"""add match engagement signal timestamps

Issue #39 (feedback loop): four nullable engagement timestamps on `match` —
`first_opened_at` (job-detail open), `clicked_apply_at` (external apply-URL
click through /api/matches/{id}/apply), `saved_at` (explicit save), and
`dismissed_at` (explicit dismiss). First-write-wins; `unsave`/`undismiss`
signal kinds NULL the stored timestamps back.

No data migration: engagement history starts at deploy time. Downgrade is
destructive — signal history is unrecoverable.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    for name in ("first_opened_at", "clicked_apply_at", "saved_at", "dismissed_at"):
        op.add_column("match", sa.Column(name, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for name in ("dismissed_at", "saved_at", "clicked_apply_at", "first_opened_at"):
        op.drop_column("match", name)
