"""add match.hybrid score columns (skill, recency, salary); relax vector_score

Issue #37: hybrid scoring. `match` gains per-row SQL-computed sub-scores so
final_score can blend skill overlap, recency decay, and salary fit instead of
only vector + LLM vibe. No data migration needed for the sub-scores — every
existing row is refreshed (rescore runs on the next search / profile save).

`vector_score` becomes nullable: un-embedded postings are no longer excluded
from the corpus; they persist a NULL vector score and a weight-renormalized
skill+recency+salary final_score. Downgrade deletes those fallback rows
(destructive for them — their scores are re-derivable by re-running the
pipeline, but the vector score cannot be synthesized without an embedding),
then restores NOT NULL and drops the new columns.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("match", sa.Column("skill_score", sa.Float(), nullable=True))
    op.add_column("match", sa.Column("recency_score", sa.Float(), nullable=True))
    op.add_column("match", sa.Column("salary_score", sa.Float(), nullable=True))
    op.alter_column("match", "vector_score", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM match WHERE vector_score IS NULL")
    op.alter_column("match", "vector_score", existing_type=sa.Float(), nullable=False)
    op.drop_column("match", "salary_score")
    op.drop_column("match", "recency_score")
    op.drop_column("match", "skill_score")
