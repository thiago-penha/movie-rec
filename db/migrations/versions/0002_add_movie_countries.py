"""Add movies.countries (production countries, ISO 3166-1 codes).

Existing rows get an empty list; re-run the seed to fill it.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-28 15:16:41.291423
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "movies",
        sa.Column("countries", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("movies", "countries")
