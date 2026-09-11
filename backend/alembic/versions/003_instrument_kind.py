"""instrument kind: share, fund, metal

Revision ID: 003_instrument_kind
Revises: 002_forecast_path
Create Date: 2026-09-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_instrument_kind"
down_revision: Union[str, None] = "002_forecast_path"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="share"),
    )
    op.create_index("ix_instruments_kind", "instruments", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_instruments_kind", table_name="instruments")
    op.drop_column("instruments", "kind")
